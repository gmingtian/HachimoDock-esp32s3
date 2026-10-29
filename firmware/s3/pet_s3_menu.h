#pragma once
#include <stdbool.h>
#include <stdint.h>
#define PET_S3_MENU_VISIBLE_ROWS 7
typedef struct {
  bool visible;
  unsigned selected,count,first;
  char title[48];
  char rows[PET_S3_MENU_VISIBLE_ROWS][64];
  bool pointer_visible,pointer_down;
  int pointer_x,pointer_y;
} pet_s3_menu_view_t;
/* Renderer and input process run under the shared runtime state mutex. */
bool pet_s3_menu_snapshot(pet_s3_menu_view_t *out);
