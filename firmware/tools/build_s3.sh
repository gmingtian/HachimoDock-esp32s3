#!/usr/bin/env bash
set -euo pipefail
task_repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
task_profile=${HACHIMO_S3_DISPLAY_PROFILE:-landscape-left}
task_spi_hz=${HACHIMO_S3_LCD_SPI_HZ:-40000000}
case "$task_spi_hz" in
  40000000|80000000) ;;
  *) echo "不支持的 LCD SPI 频率：$task_spi_hz" >&2; exit 1 ;;
esac
case "$task_profile" in
  square) task_suffix="" ;;
  landscape-left) task_suffix="-landscape-left" ;;
  *) echo "不支持的屏幕配置：$task_profile" >&2; exit 1 ;;
esac
task_build=${HACHIMO_S3_BUILD_DIR:-"$task_repo/artifacts/s3${task_suffix}-build"}
task_output=${HACHIMO_S3_OUTPUT_DIR:-"$task_repo/artifacts/s3${task_suffix}"}
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
idf.py -C "$task_repo/firmware" -B "$task_build" -DIDF_TARGET=esp32s3 -DPET_S3_DISPLAY_PROFILE="$task_profile" -DPET_S3_LCD_SPI_HZ="$task_spi_hz" build
python "$task_repo/firmware/tools/build_s3_factory.py" --build-dir "$task_build" \
  --output "$task_output/hachimodock-s3-factory.bin" \
  --spiffsgen "$IDF_PATH/components/spiffs/spiffsgen.py" --display-profile "$task_profile"
cp "$task_build/pet_manager_s3_runtime.bin" "$task_output/hachimodock-s3-app.bin"
printf '%s\n' "构建及打包完成：$task_output；未连接或写入开发板。"
printf '%s\n' "桌面端嵌入固件未改动；发布前请单独核对版本、目标与 SHA256。"
