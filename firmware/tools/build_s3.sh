#!/usr/bin/env bash
set -euo pipefail
task_repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
task_build=${HACHIMO_S3_BUILD_DIR:-"$task_repo/artifacts/s3-build"}
task_output=${HACHIMO_S3_OUTPUT_DIR:-"$task_repo/artifacts/s3"}
if [[ -z ${IDF_PATH:-} ]]; then
  task_local_idf="$HOME/.cache/xiaozhi-build/esp-idf-v6.1-cn"
  if [[ ! -f "$task_local_idf/export.sh" ]]; then
    echo "请先加载 ESP-IDF 6.1：source /path/to/esp-idf/export.sh" >&2
    exit 1
  fi
  export IDF_TOOLS_PATH=${IDF_TOOLS_PATH:-"$HOME/.cache/xiaozhi-build/tools"}
  task_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin"
  [[ ! -d $task_python ]] || export PATH="$task_python:$PATH"
  source "$task_local_idf/export.sh"
fi
export IDF_PY_BUILD_JOBS=${IDF_PY_BUILD_JOBS:-6}
export IDF_COMPONENT_CACHE_PATH=${IDF_COMPONENT_CACHE_PATH:-"$task_repo/artifacts/idf-component-cache"}
mkdir -p "$task_output"
idf.py -C "$task_repo/firmware" -B "$task_build" -DIDF_TARGET=esp32s3 build
python "$task_repo/firmware/tools/build_s3_factory.py" --build-dir "$task_build" \
  --output "$task_output/hachimodock-s3-factory.bin" \
  --spiffsgen "$IDF_PATH/components/spiffs/spiffsgen.py"
cp "$task_build/pet_manager_s3_runtime.bin" "$task_output/hachimodock-s3-app.bin"
mkdir -p "$task_repo/pc/src-tauri/firmware/esp32-s3"
cp "$task_output/hachimodock-s3-app.bin" "$task_repo/pc/src-tauri/firmware/esp32-s3/firmware.bin"
printf '%s\n' "构建及打包完成：$task_output；未连接或写入开发板。"
