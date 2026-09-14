/****************************************************************************
 * drivers/video/qemu_camera.c
 *
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.  The
 * ASF licenses this file to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance with the
 * License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations
 * under the License.
 *
 ****************************************************************************/

/****************************************************************************
 * QEMU "virtual camera"
 *
 * The qemu ARM64 virtual board has no physical camera and no Android-emulator
 * "goldfish pipe" camera host service, so this driver synthesizes frames in
 * software.  It follows the same imgdata + imgsensor pattern as the NuttX
 * sim/goldfish camera drivers and plugs into the V4L2 capture framework:
 *
 *   drivers_initialize() -> qemu_camera_initialize()
 *     - registers the image data + image sensor
 *     - capture_initialize("/dev/video") creates the /dev/video capture node
 *
 * A kernel "camera" thread is started on the first capture (STREAMON) and,
 * while streaming, periodically fills the next queued frame buffer with a
 * generated RGB565 test pattern and signals the capture framework - exactly
 * what an image sensor would do with real pixels.
 *
 ****************************************************************************/

/****************************************************************************
 * Included Files
 ****************************************************************************/

#include <nuttx/config.h>

#if defined(CONFIG_VIDEO_QEMU_CAMERA) && defined(CONFIG_VIDEO_STREAM)

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

#include <nuttx/kthread.h>
#include <nuttx/signal.h>
#include <nuttx/spinlock.h>
#include <nuttx/video/imgdata.h>
#include <nuttx/video/imgsensor.h>
#include <nuttx/video/v4l2_cap.h>
#include <nuttx/video/video.h>

/****************************************************************************
 * Pre-processor Definitions
 ****************************************************************************/

#define QEMU_CAMERA_DEV_PATH   "/dev/video"
#define QEMU_CAMERA_DRV_NAME   "QEMU Virtual Camera"

/* Frame period / size (QVGA RGB565, like the NuttX camera example). */

#define QEMU_CAMERA_FRAME_MS    100  /* ~10 fps */
#define QEMU_CAMERA_WIDTH       320
#define QEMU_CAMERA_HEIGHT      240

#define QEMU_CAMERA_PRIORITY    100
#define QEMU_CAMERA_STACKSIZE   2048

/****************************************************************************
 * Private Types
 ****************************************************************************/

typedef struct
{
  struct imgdata_s       data;       /* must be first (container_of) */
  struct imgsensor_s     sensor;
  imgdata_capture_t      capture_cb;
  FAR void              *capture_arg;
  FAR uint8_t           *next_buf;
  uint32_t               buf_size;
  uint16_t               width;
  uint16_t               height;
  uint32_t               frame;
  bool                   streaming;
  pid_t                  pid;
} qemu_camera_priv_t;

/****************************************************************************
 * Private Function Prototypes
 ****************************************************************************/

static int qemu_camera_thread(int argc, FAR char *argv[]);

/* Image sensor operations (mostly dummy for a virtual camera). */

static bool qemu_camera_is_available(FAR struct imgsensor_s *sensor);
static int qemu_camera_sensor_init(FAR struct imgsensor_s *sensor);
static int qemu_camera_sensor_uninit(FAR struct imgsensor_s *sensor);
static FAR const char *
qemu_camera_get_driver_name(FAR struct imgsensor_s *sensor);
static int
qemu_camera_sensor_validate_frame_setting(FAR struct imgsensor_s *sensor,
                                          imgsensor_stream_type_t type,
                                          uint8_t nr_datafmt,
                                          FAR imgsensor_format_t *datafmts,
                                          FAR imgsensor_interval_t *interval);
static int qemu_camera_sensor_start_capture(FAR struct imgsensor_s *sensor,
                                            imgsensor_stream_type_t type,
                                            uint8_t nr_datafmt,
                                            FAR imgsensor_format_t *datafmts,
                                            FAR imgsensor_interval_t *interval);
static int qemu_camera_sensor_stop_capture(FAR struct imgsensor_s *sensor,
                                           imgsensor_stream_type_t type);

/* Image data operations (do the real work). */

static int qemu_camera_data_init(FAR struct imgdata_s *data);
static int qemu_camera_data_uninit(FAR struct imgdata_s *data);
static int qemu_camera_data_set_buf(FAR struct imgdata_s *data,
                                    uint8_t nr_datafmts,
                                    FAR imgdata_format_t *datafmts,
                                    FAR uint8_t *addr,
                                    uint32_t size);
static int
qemu_camera_data_validate_frame_setting(FAR struct imgdata_s *data,
                                        uint8_t nr_datafmt,
                                        FAR imgdata_format_t *datafmt,
                                        FAR imgdata_interval_t *interval);
static int qemu_camera_data_start_capture(FAR struct imgdata_s *data,
                                          uint8_t nr_datafmt,
                                          FAR imgdata_format_t *datafmt,
                                          FAR imgdata_interval_t *interval,
                                          imgdata_capture_t callback,
                                          FAR void *arg);
static int qemu_camera_data_stop_capture(FAR struct imgdata_s *data);

/****************************************************************************
 * Private Data
 ****************************************************************************/

static const struct v4l2_frmsizeenum g_qemu_camera_frmsizes[] =
{
  {
    .type = V4L2_FRMSIZE_TYPE_DISCRETE,
    .discrete =
    {
      .width = QEMU_CAMERA_WIDTH,
      .height = QEMU_CAMERA_HEIGHT,
    }
  },
  {
    .type = V4L2_FRMSIZE_TYPE_DISCRETE,
    .discrete =
    {
      .width = 640,
      .height = 480,
    }
  }
};

static const struct v4l2_fmtdesc g_qemu_camera_fmtdescs[] =
{
  {
    .pixelformat = V4L2_PIX_FMT_RGB565,
    .description = "RGB565",
  }
};

static const struct imgsensor_ops_s g_qemu_camera_sensor_ops =
{
  .is_available           = qemu_camera_is_available,
  .init                   = qemu_camera_sensor_init,
  .uninit                 = qemu_camera_sensor_uninit,
  .get_driver_name        = qemu_camera_get_driver_name,
  .validate_frame_setting = qemu_camera_sensor_validate_frame_setting,
  .start_capture          = qemu_camera_sensor_start_capture,
  .stop_capture           = qemu_camera_sensor_stop_capture,
};

static const struct imgdata_ops_s g_qemu_camera_data_ops =
{
  .init                   = qemu_camera_data_init,
  .uninit                 = qemu_camera_data_uninit,
  .set_buf                = qemu_camera_data_set_buf,
  .validate_frame_setting = qemu_camera_data_validate_frame_setting,
  .start_capture          = qemu_camera_data_start_capture,
  .stop_capture           = qemu_camera_data_stop_capture,
};

static qemu_camera_priv_t g_qemu_camera_priv =
{
  .data =
  {
    &g_qemu_camera_data_ops
  },
  .sensor =
  {
    .ops = &g_qemu_camera_sensor_ops,
    .frmsizes_num = 2,
    .frmsizes = g_qemu_camera_frmsizes,
    .fmtdescs_num = 1,
    .fmtdescs = g_qemu_camera_fmtdescs,
  },
  .width = QEMU_CAMERA_WIDTH,
  .height = QEMU_CAMERA_HEIGHT,
};

/****************************************************************************
 * Private Functions
 ****************************************************************************/

/* Fill a frame buffer with a moving RGB565 test pattern so successive
 * "camera frames" are visibly different.
 */

static void qemu_camera_fill(FAR uint8_t *buf, uint32_t bufsize,
                             uint16_t width, uint16_t height,
                             uint32_t frame)
{
  uint32_t i;
  uint32_t frame_size;
  uint16_t pix;
  uint16_t x;
  uint16_t y;

  if (width == 0 || height == 0)
    {
      width = QEMU_CAMERA_WIDTH;
      height = QEMU_CAMERA_HEIGHT;
    }

  frame_size = (uint32_t)width * height * 2;
  if (bufsize > frame_size)
    {
      bufsize = frame_size;
    }

  i = 0;
  if (bufsize == frame_size)
    {
      for (y = 0; y < height; y++)
        {
          for (x = 0; x < width; x++)
            {
              uint16_t r = ((uint16_t)((x * 32u) / width)) & 31u;
              uint16_t g = ((uint16_t)((y * 64u) / height)) & 63u;
              uint16_t b = ((uint16_t)(x + y + frame * 3u)) & 31u;

              pix = (uint16_t)((r << 11) | (g << 5) | b);
              buf[i++] = (uint8_t)(pix & 0xff);
              buf[i++] = (uint8_t)((pix >> 8) & 0xff);
            }
        }
    }
  else
    {
      for (i = 0; i < bufsize; i++)
        {
          buf[i] = (uint8_t)(i + frame);
        }
    }
}

/****************************************************************************
 * Name: qemu_camera_thread
 *
 *   "Camera" producer: while streaming, fill the next queued frame buffer and
 *   notify the capture framework.  Started lazily on the first STREAMON.
 ****************************************************************************/

static int qemu_camera_thread(int argc, FAR char *argv[])
{
  FAR qemu_camera_priv_t *priv = &g_qemu_camera_priv;
  struct timespec ts;
  struct timeval tv;
  irqstate_t flags;

  while (priv->streaming)
    {
      nxsig_usleep(QEMU_CAMERA_FRAME_MS * 1000);

      if (priv->next_buf != NULL && priv->capture_cb != NULL)
        {
          flags = irq_save_nopreempt();

          qemu_camera_fill(priv->next_buf, priv->buf_size, priv->width,
                           priv->height, priv->frame++);

          clock_gettime(CLOCK_MONOTONIC, &ts);
          TIMESPEC_TO_TIMEVAL(&tv, &ts);

          priv->capture_cb(0, priv->buf_size, &tv, priv->capture_arg);

          irq_restore_nopreempt(flags);
        }
    }

  priv->pid = 0;
  return OK;
}

/* Sensor ops */

static bool qemu_camera_is_available(FAR struct imgsensor_s *sensor)
{
  return true;
}

static int qemu_camera_sensor_init(FAR struct imgsensor_s *sensor)
{
  return OK;
}

static int qemu_camera_sensor_uninit(FAR struct imgsensor_s *sensor)
{
  return OK;
}

static FAR const char *
qemu_camera_get_driver_name(FAR struct imgsensor_s *sensor)
{
  return QEMU_CAMERA_DRV_NAME;
}

static int
qemu_camera_sensor_validate_frame_setting(FAR struct imgsensor_s *sensor,
                                          imgsensor_stream_type_t type,
                                          uint8_t nr_datafmt,
                                          FAR imgsensor_format_t *datafmts,
                                          FAR imgsensor_interval_t *interval)
{
  return OK;
}

static int qemu_camera_sensor_start_capture(FAR struct imgsensor_s *sensor,
                                            imgsensor_stream_type_t type,
                                            uint8_t nr_datafmt,
                                            FAR imgsensor_format_t *datafmts,
                                            FAR imgsensor_interval_t *interval)
{
  return OK;
}

static int qemu_camera_sensor_stop_capture(FAR struct imgsensor_s *sensor,
                                           imgsensor_stream_type_t type)
{
  return OK;
}

/* Data ops */

static int qemu_camera_data_init(FAR struct imgdata_s *data)
{
  FAR qemu_camera_priv_t *priv = (FAR qemu_camera_priv_t *)data;

  priv->width = QEMU_CAMERA_WIDTH;
  priv->height = QEMU_CAMERA_HEIGHT;
  return OK;
}

static int qemu_camera_data_uninit(FAR struct imgdata_s *data)
{
  return OK;
}

static int qemu_camera_data_set_buf(FAR struct imgdata_s *data,
                                    uint8_t nr_datafmts,
                                    FAR imgdata_format_t *datafmts,
                                    FAR uint8_t *addr,
                                    uint32_t size)
{
  FAR qemu_camera_priv_t *priv = (FAR qemu_camera_priv_t *)data;

  if (addr == NULL || ((uintptr_t)addr & 0x1f))
    {
      return -EINVAL;
    }

  priv->next_buf = addr;
  priv->buf_size = size;
  return OK;
}

static int
qemu_camera_data_validate_frame_setting(FAR struct imgdata_s *data,
                                        uint8_t nr_datafmt,
                                        FAR imgdata_format_t *datafmt,
                                        FAR imgdata_interval_t *interval)
{
  if (nr_datafmt > IMGDATA_FMT_MAX)
    {
      return -ENOTSUP;
    }

  return OK;
}

static int qemu_camera_data_start_capture(FAR struct imgdata_s *data,
                                          uint8_t nr_datafmt,
                                          FAR imgdata_format_t *datafmt,
                                          FAR imgdata_interval_t *interval,
                                          imgdata_capture_t callback,
                                          FAR void *arg)
{
  FAR qemu_camera_priv_t *priv = (FAR qemu_camera_priv_t *)data;
  int ret;

  if (nr_datafmt > 0 && datafmt != NULL)
    {
      priv->width = datafmt[IMGDATA_FMT_MAIN].width;
      priv->height = datafmt[IMGDATA_FMT_MAIN].height;
    }

  if (priv->pid <= 0)
    {
      ret = kthread_create("qemu_camera", QEMU_CAMERA_PRIORITY,
                           QEMU_CAMERA_STACKSIZE, qemu_camera_thread, NULL);
      if (ret < 0)
        {
          return ret;
        }

      priv->pid = ret;
    }

  priv->capture_cb = callback;
  priv->capture_arg = arg;
  priv->streaming = true;
  return OK;
}

static int qemu_camera_data_stop_capture(FAR struct imgdata_s *data)
{
  FAR qemu_camera_priv_t *priv = (FAR qemu_camera_priv_t *)data;

  priv->streaming = false;
  priv->next_buf = NULL;
  return OK;
}

/****************************************************************************
 * Public Functions
 ****************************************************************************/

/****************************************************************************
 * Name: qemu_camera_initialize
 *
 *   Register the virtual camera image sensor/data and create the /dev/video
 *   capture node.  Called from drivers_initialize().
 ****************************************************************************/

int qemu_camera_initialize(void)
{
  FAR qemu_camera_priv_t *priv = &g_qemu_camera_priv;
  int ret;

  ret = imgsensor_register(&priv->sensor);
  if (ret < 0)
    {
      return ret;
    }

  imgdata_register(&priv->data);

  ret = capture_initialize(QEMU_CAMERA_DEV_PATH);
  if (ret < 0)
    {
      return ret;
    }

  return OK;
}

#endif /* CONFIG_VIDEO_QEMU_CAMERA && CONFIG_VIDEO_STREAM */
