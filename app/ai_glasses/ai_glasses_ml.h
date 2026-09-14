/****************************************************************************
 * apps/examples/ai_glasses/ai_glasses_ml.h
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

#ifndef __APPS_EXAMPLES_AI_GLASSES_ML_H
#define __APPS_EXAMPLES_AI_GLASSES_ML_H

/****************************************************************************
 * Included Files
 ****************************************************************************/

#include <stdint.h>

/* Model input: 96 x 96 x 1 greyscale. */

#define AI_GLASSES_ML_COLS    96
#define AI_GLASSES_ML_ROWS    96
#define AI_GLASSES_ML_CHANS   1

#define AI_GLASSES_ML_CLASSES 2
#define AI_GLASSES_ML_NOTPERSON 0
#define AI_GLASSES_ML_PERSON    1

#ifdef __cplusplus
#define EXTERN extern "C"
extern "C"
{
#else
#define EXTERN extern
#endif

struct ai_glasses_ml_result_s
{
  int class_id;             /* winning class (0 = notperson, 1 = person)  */
  float confidence;         /* softmax confidence of the winning class     */
  float conf[AI_GLASSES_ML_CLASSES]; /* softmax confidences                */
  char label[16];           /* winning label ("person"/"notperson")        */
};

int ai_glasses_ml_init(void);
int ai_glasses_ml_run(const uint8_t *gray,
                      struct ai_glasses_ml_result_s *res);

#undef EXTERN
#ifdef __cplusplus
}
#endif

#endif /* __APPS_EXAMPLES_AI_GLASSES_ML_H */
