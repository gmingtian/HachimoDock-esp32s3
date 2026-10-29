#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "cJSON.h"
#define PET_S3_WIFI_PORT 48973
/* The network task alone owns sockets/TLS. Callbacks only enqueue protocol work. */
typedef bool (*pet_s3_wifi_rx_fn)(uintptr_t,const uint8_t *,size_t);
esp_err_t pet_s3_wifi_init(const char *,pet_s3_wifi_rx_fn);
uintptr_t pet_s3_connection_token(unsigned route);
bool pet_s3_wifi_send(uintptr_t,const char *);
void pet_s3_wifi_close(uintptr_t);
bool pet_s3_wifi_auth(const cJSON *);
void pet_s3_wifi_authenticated(uintptr_t);
/* Caller serializes these operations with protocol state. */
bool pet_s3_wifi_maintenance(const char *,const cJSON *,bool,bool,void (*)(const char *,void *),void *);
void pet_s3_wifi_menu_status(char *,size_t);
bool pet_s3_wifi_menu_action(unsigned); /* 1 toggle, 2 revoke, 3 clear */
