# ##############################################################################
# apps/examples/ai_glasses/CMakeLists.txt
#
# Licensed to the Apache Software Foundation (ASF) under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  The ASF licenses this
# file to you under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.
#
# ##############################################################################

if(CONFIG_EXAMPLES_AI_GLASSES)
  nuttx_add_application(
    MODULE
    ${CONFIG_EXAMPLES_AI_GLASSES}
    NAME
    ${CONFIG_EXAMPLES_AI_GLASSES_PROGNAME}
    SRCS
    ai_glasses_main.c
    ai_glasses_ml.cpp
    STACKSIZE
    65536
    HEAPSIZE
    ${CONFIG_EXAMPLES_AI_GLASSES_HEAPSIZE}
    PRIORITY
    ${CONFIG_EXAMPLES_AI_GLASSES_PRIORITY})
  if(CONFIG_TFLITEMICRO)
    target_link_libraries(apps_ai_glasses PUBLIC tflite_micro)
    target_compile_definitions(apps_ai_glasses PRIVATE
      TF_LITE_STATIC_MEMORY
      TF_LITE_STRIP_ERROR_STRINGS
      TFLITE_WITH_STABLE_ABI=0
      TFLITE_USE_OPAQUE_DELEGATE=0
      TFLITE_SINGLE_ROUNDING=0)
  endif()
endif()
