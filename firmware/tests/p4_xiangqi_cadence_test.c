/* Differential 8ms/2ms driver: real game adapter, changing legal positions. */
#include "pet_p4_game.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(2);}}while(0)
static pet_p4_game_engine_t game;

int main(int argc,char **argv){
  CHECK(argc==2);unsigned interval=(unsigned)strtoul(argv[1],NULL,10);
  CHECK(interval==2U||interval==8U);
  unsigned replies=0;uint64_t total_ms=0;
  for(unsigned level=0;level<3;level++){
    uint64_t now=100;uint32_t random=0x12345678U+level;
    CHECK(pet_p4_game_configure(&game,PET_P4_GAME_XIANGQI,100,77));
    if(level!=1U)CHECK(pet_p4_game_command(&game,level==0U?PET_P4_GAME_COMMAND_NORTH:PET_P4_GAME_COMMAND_SOUTH,++now));
    CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,++now));
    for(unsigned round=0;round<12U&&!game.game_over;round++){
      unsigned from[128],to[128],count=0;
      for(unsigned f=0;f<90U;f++)if(game.xiangqi.board[f]&&game.xiangqi.board[f]<=7U)
        for(unsigned t=0;t<90U;t++)if(pet_p4_xiangqi_is_legal(&game.xiangqi,f,t)){
          CHECK(count<128U);from[count]=f;to[count]=t;count++;
        }
      CHECK(count>0U);random=random*1664525U+1013904223U;unsigned choice=random%count;
      game.xiangqi.cursor=(uint8_t)from[choice];
      CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,++now));
      game.xiangqi.cursor=(uint8_t)to[choice];
      CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,++now));
      if(!game.xiangqi.ai_pending){CHECK(game.game_over);break;}
      uint8_t submitted[90];memcpy(submitted,game.xiangqi.board,90);
      uint64_t began=now;uint32_t work=game.xiangqi.ai_work;
      CHECK(!pet_p4_game_process(&game,began+interval-1U));
      CHECK(game.xiangqi.ai_work==work);
      uint32_t frame_revision=game.frame.revision;
      now=began+interval;
      bool visible=pet_p4_game_process(&game,now);
      CHECK(game.xiangqi.ai_work>0U&&game.xiangqi.ai_work<=256U);
      if(!visible)CHECK(game.frame.revision==frame_revision);
      work=game.xiangqi.ai_work;
      CHECK(!pet_p4_game_process(&game,now));CHECK(game.xiangqi.ai_work==work);
      while(game.xiangqi.ai_pending){
        CHECK(now-began<100000U);
        CHECK(!memcmp(submitted,game.xiangqi.board,90));
        (void)pet_p4_game_process(&game,++now);
        CHECK(game.xiangqi.ai_slice_work<=256U);
      }
      total_ms+=now-began;replies++;
      CHECK(game.xiangqi.ai_target_depth==level+1U);
      CHECK(game.xiangqi.ai_completed_depth<=game.xiangqi.ai_target_depth);
      printf("P %u %u %u %u %u %u %u %u %u ",level,round,
        (unsigned)game.xiangqi.ai_completed_depth,(unsigned)game.xiangqi.ai_target_depth,
        (unsigned)game.xiangqi.ai_work,(unsigned)game.xiangqi.ai_nodes,
        (unsigned)game.xiangqi.status,(unsigned)game.xiangqi.last_from,(unsigned)game.xiangqi.last_to);
      for(unsigned at=0;at<90U;at++)printf("%02x",(unsigned)game.xiangqi.board[at]);
      puts("");
      /* Even a huge elapsed interval runs one bounded slice, no catch-up burst. */
      if(round==0U){
        CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_UNDO,++now));
        game.xiangqi.cursor=(uint8_t)from[choice];
        CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,++now));
        game.xiangqi.cursor=(uint8_t)to[choice];
        CHECK(pet_p4_game_command(&game,PET_P4_GAME_COMMAND_PLACE,++now));
        (void)pet_p4_game_process(&game,now+100000U);now+=100000U;
        CHECK(game.xiangqi.ai_work>0U&&game.xiangqi.ai_work<=256U);
        while(game.xiangqi.ai_pending){(void)pet_p4_game_process(&game,++now);CHECK(game.xiangqi.ai_slice_work<=256U);}
      }
    }
  }
  CHECK(replies>=12U);printf("T %u %llu\n",replies,(unsigned long long)total_ms);
  return 0;
}
