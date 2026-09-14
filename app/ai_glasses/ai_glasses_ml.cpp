/****************************************************************************
 * apps/examples/ai_glasses/ai_glasses_ml.cpp
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
 * TensorFlow Lite Micro inference for the person_detect model
 * (Visual Wake Words, int8, 96 x 96 x 1).  Exposes a C ABI to the C part of
 * the ai_glasses example.  Objects are constructed in-place so the code has
 * no dependency on C++ static-constructor ordering inside the ELF module.
 ****************************************************************************/

#include "ai_glasses_ml.h"

#include <new>

#include <cmath>
#include <cstring>

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_log.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/system_setup.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "person_detect_model_data.h"

namespace
{
  constexpr int kTensorArenaSize = 136 * 1024;
  alignas(16) uint8_t g_tensor_arena[kTensorArenaSize];

  const tflite::Model *g_model = nullptr;
  tflite::MicroInterpreter *g_interpreter = nullptr;
  TfLiteTensor *g_input = nullptr;
  TfLiteTensor *g_output = nullptr;
  bool g_ready = false;

  alignas(tflite::MicroMutableOpResolver<8>) uint8_t g_resolver_buf[
      sizeof(tflite::MicroMutableOpResolver<8>)];
  alignas(tflite::MicroInterpreter) uint8_t g_interp_buf[
      sizeof(tflite::MicroInterpreter)];
}

extern "C" int ai_glasses_ml_init(void)
{
  if (g_ready)
    {
      return 0;
    }

  tflite::InitializeTarget();

  g_model = tflite::GetModel(g_person_detect_model_data);
  if (g_model == nullptr || g_model->version() != TFLITE_SCHEMA_VERSION)
    {
      MicroPrintf("ai_glasses: person_detect schema version mismatch");
      return -1;
    }

  auto *resolver = new (g_resolver_buf) tflite::MicroMutableOpResolver<8>();
  resolver->AddAveragePool2D(tflite::Register_AVERAGE_POOL_2D_INT8());
  resolver->AddConv2D(tflite::Register_CONV_2D_INT8());
  resolver->AddDepthwiseConv2D(tflite::Register_DEPTHWISE_CONV_2D_INT8());
  resolver->AddReshape();
  resolver->AddSoftmax(tflite::Register_SOFTMAX_INT8());

  g_interpreter = new (g_interp_buf) tflite::MicroInterpreter(
      g_model, *resolver, g_tensor_arena, kTensorArenaSize);
  if (g_interpreter->AllocateTensors() != kTfLiteOk)
    {
      MicroPrintf("ai_glasses: AllocateTensors() failed");
      return -1;
    }

  g_input = g_interpreter->input(0);
  g_output = g_interpreter->output(0);
  g_ready = true;
  return 0;
}

extern "C" int ai_glasses_ml_run(const uint8_t *gray,
                                 struct ai_glasses_ml_result_s *res)
{
  int numel = AI_GLASSES_ML_ROWS * AI_GLASSES_ML_COLS * AI_GLASSES_ML_CHANS;
  int i;
  int out_class;
  float in_scale;
  int in_zero;
  float out_scale;
  int out_zero;
  float logits[AI_GLASSES_ML_CLASSES];
  float maxv;
  float sum;
  float p[AI_GLASSES_ML_CLASSES];

  if (!g_ready)
    {
      return -1;
    }

  if (res == NULL)
    {
      return -1;
    }

  /* Quantize the [0..255] greyscale image into the int8 input tensor using the
   * tensor's own quantization parameters (image is normalized to [0, 1]). */

  in_scale = g_input->params.scale;
  in_zero = g_input->params.zero_point;
  if (g_input->type == kTfLiteInt8)
    {
      int8_t *q = g_input->data.int8;
      for (i = 0; i < numel; i++)
        {
          float v = (float)gray[i] / 255.0f;
          int val = (int)std::lround(v / in_scale) + in_zero;

          if (val < -128)
            {
              val = -128;
            }
          else if (val > 127)
            {
              val = 127;
            }

          q[i] = (int8_t)val;
        }
    }
  else
    {
      memcpy(g_input->data.uint8, gray, numel);
    }

  if (g_interpreter->Invoke() != kTfLiteOk)
    {
      MicroPrintf("ai_glasses: Invoke() failed");
      return -1;
    }

  /* Dequantize the two output logits and run a softmax for confidence. */

  out_scale = g_output->params.scale;
  out_zero = g_output->params.zero_point;
  for (i = 0; i < AI_GLASSES_ML_CLASSES; i++)
    {
      logits[i] = ((float)g_output->data.int8[i] - (float)out_zero) *
                  out_scale;
    }

  maxv = logits[0];
  for (i = 1; i < AI_GLASSES_ML_CLASSES; i++)
    {
      if (logits[i] > maxv)
        {
          maxv = logits[i];
        }
    }

  sum = 0.0f;
  for (i = 0; i < AI_GLASSES_ML_CLASSES; i++)
    {
      p[i] = std::exp(logits[i] - maxv);
      sum += p[i];
    }

  out_class = 0;
  for (i = 0; i < AI_GLASSES_ML_CLASSES; i++)
    {
      p[i] /= sum;
      res->conf[i] = p[i];
      if (p[i] > p[out_class])
        {
          out_class = i;
        }
    }

  res->class_id = out_class;
  res->confidence = p[out_class];
  strncpy(res->label, out_class == AI_GLASSES_ML_PERSON ?
                      "person" : "notperson", sizeof(res->label) - 1);
  res->label[sizeof(res->label) - 1] = '\0';
  return 0;
}
