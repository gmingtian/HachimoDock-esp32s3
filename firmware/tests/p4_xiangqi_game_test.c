#include "pet_p4_game.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static pet_p4_game_engine_t game;
int main(void){
  pet_p4_game_kind_t kind=pet_p4_game_kind_from_name("xiangqi");
  assert((unsigned)kind==6);
  assert(!strcmp(pet_p4_game_kind_name(kind),"xiangqi"));
  assert(pet_p4_game_configure(&game,kind,100,17));
  pet_p4_game_frame_t f;pet_p4_game_get_frame(&game,&f);
  assert(f.width==9&&f.height==10&&f.score==16&&!f.running);
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,1));
  assert(game.running&&!game.game_over);
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_NORTH,2));
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_UNDO,3)==false);
  /* Return to the opening soldier, select it, follow its legal guide and move. */
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_SOUTH,4));
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,5));
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_NORTH,6));
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,7));
  assert(game.xiangqi.ai_pending&&game.score==19);
  uint32_t work=game.xiangqi.ai_work,revision=game.frame.revision;
  assert(!pet_p4_game_process(&game,14));
  assert(game.xiangqi.ai_work==work);
  bool visible=pet_p4_game_process(&game,100000);
  assert(game.xiangqi.ai_work>work&&game.xiangqi.ai_work-work<=256);
  assert(game.xiangqi.ai_slice_work<=256);
  if(!visible)assert(game.frame.revision==revision);
  work=game.xiangqi.ai_work;
  assert(!pet_p4_game_process(&game,100000));
  assert(game.xiangqi.ai_work==work);
  assert(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_UNDO,100001));
  assert(!game.xiangqi.ai_pending&&game.score==17);
  puts("xiangqi game adapter passed");return 0;
}
