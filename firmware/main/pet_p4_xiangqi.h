/*
 * [Input] Semantic joystick commands and a bounded search work allowance.
 * [Output] Heap-free 9x10 Xiangqi state and legal-destination frame bits.
 * [Pos] Standalone offline rules/UI/search core; side 0 red, side 1 black.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PET_P4_XIANGQI_CELLS 90U
#define PET_P4_XIANGQI_NONE 255U
#define PET_P4_XIANGQI_MAX_MOVES 128U
#define PET_P4_XIANGQI_MAX_DEPTH 3U
/* A work unit advances one bounded generator/search transition. */
#define PET_P4_XIANGQI_SLICE_MAX 256U

enum {
  PET_P4_XIANGQI_READY = 0, PET_P4_XIANGQI_HUMAN,
  PET_P4_XIANGQI_SELECTED, PET_P4_XIANGQI_THINKING,
  PET_P4_XIANGQI_CHECK, PET_P4_XIANGQI_INVALID,
  PET_P4_XIANGQI_RED_WIN, PET_P4_XIANGQI_BLACK_WIN,
  PET_P4_XIANGQI_DRAW
};
enum {
  PET_P4_XIANGQI_LEFT = 1, PET_P4_XIANGQI_RIGHT,
  PET_P4_XIANGQI_UP, PET_P4_XIANGQI_DOWN,
  PET_P4_XIANGQI_SELECT, PET_P4_XIANGQI_UNDO
};
enum {
  PET_P4_XIANGQI_PIECE_MASK = 15, PET_P4_XIANGQI_CURSOR = 16,
  PET_P4_XIANGQI_SELECTION = 32, PET_P4_XIANGQI_LAST = 64,
  PET_P4_XIANGQI_LEGAL = 128
};

typedef struct {
  uint8_t from, to;
  int16_t order;
} pet_p4_xiangqi_move_t;

/* Private continuation frames are in the state to avoid heap/global ownership.
 * Valid standard material has at most 119 geometric moves, below 128. */
typedef struct {
  pet_p4_xiangqi_move_t moves[PET_P4_XIANGQI_MAX_MOVES];
  int32_t alpha, beta, best;
  uint16_t count, next;
  uint8_t scan_from, candidate, phase, side, remaining;
  uint8_t undo_from, undo_to, undo_piece, undo_capture;
  uint8_t best_from, best_to;
} pet_p4_xiangqi_search_frame_t;

typedef struct {
  /* Board bytes are always pure piece codes: 0 empty; 1..7 red KAEHRCP;
   * 8..14 black KAEHRCP. UI flags live only in get_cells() output. */
  uint8_t board[PET_P4_XIANGQI_CELLS];
  uint8_t cursor, selected, level, status, side_to_move;
  bool running, game_over, ai_pending;
  uint32_t revision;
  uint8_t last_from, last_to;
  /* Search diagnostics; ai_slice_work never exceeds SLICE_MAX. */
  uint32_t ai_nodes, ai_work, ai_slice_work, ai_work_limit;
  uint8_t ai_completed_depth, ai_target_depth;

  uint32_t rng;
  uint8_t _undo_board[PET_P4_XIANGQI_CELLS];
  uint8_t _undo_last_from, _undo_last_to, _undo_cursor;
  bool _undo_valid;
  uint8_t _search_board[PET_P4_XIANGQI_CELLS];
  pet_p4_xiangqi_search_frame_t _stack[PET_P4_XIANGQI_MAX_DEPTH + 1U];
  uint8_t _ply, _iteration_depth, _best_from, _best_to;
  bool _search_started;
} pet_p4_xiangqi_t;

void pet_p4_xiangqi_init(pet_p4_xiangqi_t *game, unsigned level, uint32_t seed);
bool pet_p4_xiangqi_command(pet_p4_xiangqi_t *game, unsigned op);
/* At most one slice, even for UINT32_MAX allowance; zero allowance is a no-op.
 * Returns a visible change, not whether hidden search work advanced. */
bool pet_p4_xiangqi_process(pet_p4_xiangqi_t *game, uint32_t work_budget);
void pet_p4_xiangqi_get_cells(const pet_p4_xiangqi_t *game, uint8_t out[90]);
int32_t pet_p4_xiangqi_ui_score(const pet_p4_xiangqi_t *game);
/* is_legal includes side_to_move and self-check; it does not require running.
 * in_check/has_legal_move side: 0 red, 1 black. Missing king is checked. */
bool pet_p4_xiangqi_is_legal(const pet_p4_xiangqi_t *game, unsigned from, unsigned to);
bool pet_p4_xiangqi_in_check(const pet_p4_xiangqi_t *game, unsigned side);
bool pet_p4_xiangqi_has_legal_move(const pet_p4_xiangqi_t *game, unsigned side);

#ifdef __cplusplus
}
#endif
