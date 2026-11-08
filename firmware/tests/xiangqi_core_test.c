#include "../main/pet_p4_xiangqi.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define AT(x,y) ((unsigned)((y)*9+(x)))
#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"FAIL %s:%d: %s\n", __FILE__,__LINE__,#expr); exit(1); } checks++; } while (0)
static unsigned checks;
static void empty(pet_p4_xiangqi_t *g) {
  pet_p4_xiangqi_init(g,1,123);
  memset(g->board,0,90); g->board[AT(3,0)]=8; g->board[AT(5,9)]=1;
  g->running=true; g->status=1; g->side_to_move=0;
}
static void play(pet_p4_xiangqi_t *g,unsigned from,unsigned to) {
  g->cursor=(uint8_t)from; CHECK(pet_p4_xiangqi_command(g,5));
  CHECK(g->selected==from); g->cursor=(uint8_t)to;
  CHECK(pet_p4_xiangqi_command(g,5));
}

/* Catches missing rule paths, swapped river orientation, wrong leg/eye cells,
 * cannon jumping without a capture, exposed kings, and false terminal results. */
static void rules(void) {
  pet_p4_xiangqi_t g;
  pet_p4_xiangqi_init(&g,1,123);
  unsigned count=0;
  for(unsigned f=0;f<90;f++) for(unsigned t=0;t<90;t++) count+=pet_p4_xiangqi_is_legal(&g,f,t)?1U:0U;
  CHECK(count==44);
  CHECK(!pet_p4_xiangqi_is_legal(&g,90,0)); CHECK(!pet_p4_xiangqi_is_legal(&g,0,90));
  empty(&g); g.board[AT(5,9)]=0;g.board[AT(4,9)]=1;g.board[AT(4,7)]=4;
  static const int horse[8][2]={{2,1},{2,-1},{-2,1},{-2,-1},{1,2},{-1,2},{1,-2},{-1,-2}};
  for(unsigned i=0;i<8;i++) {
    unsigned t=AT(4+horse[i][0],7+horse[i][1]);
    unsigned leg=AT(4+(abs(horse[i][0])==2?horse[i][0]/2:0),7+(abs(horse[i][1])==2?horse[i][1]/2:0));
    CHECK(pet_p4_xiangqi_is_legal(&g,AT(4,7),t));
    g.board[leg]=7; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,7),t));
    g.board[leg]=14; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,7),t)); g.board[leg]=0;
  }
  empty(&g); g.board[AT(2,9)]=3;
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,9),AT(4,7)));
  g.board[AT(3,8)]=7; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,9),AT(4,7)));
  g.board[AT(3,8)]=14; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,9),AT(4,7)));
  empty(&g); g.board[AT(4,5)]=3; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,5),AT(6,3)));
  empty(&g); g.board[AT(4,4)]=10; g.side_to_move=1; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,4),AT(6,6)));
  empty(&g); g.board[AT(3,9)]=2; CHECK(pet_p4_xiangqi_is_legal(&g,AT(3,9),AT(4,8)));
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(3,9),AT(2,8)));
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(5,9),AT(6,9))); CHECK(!pet_p4_xiangqi_is_legal(&g,AT(5,9),AT(4,8)));
  empty(&g); g.board[AT(0,6)]=5; g.board[AT(0,0)]=12;
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,0)));
  g.board[AT(0,3)]=7; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,0)));
  empty(&g); g.board[AT(0,6)]=6; g.board[AT(0,0)]=12;
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,0)));
  g.board[AT(0,3)]=7; CHECK(pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,0)));
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,1)));
  g.board[AT(0,2)]=14; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(0,6),AT(0,0)));
  empty(&g); g.board[AT(2,5)]=7; CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,5),AT(3,5)));
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,5),AT(2,4)));
  g.board[AT(2,5)]=0;g.board[AT(2,4)]=7;CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,4),AT(3,4)));
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,4),AT(2,5)));
  g.board[AT(2,0)]=7;CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,0),AT(1,0)));CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,0),AT(2,1)));
  empty(&g);g.board[AT(2,4)]=14;g.side_to_move=1;CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,4),AT(3,4)));
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,4),AT(2,5)));g.board[AT(2,4)]=0;g.board[AT(2,5)]=14;
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(2,5),AT(3,5)));CHECK(!pet_p4_xiangqi_is_legal(&g,AT(2,5),AT(2,4)));
  empty(&g);g.board[AT(3,0)]=0;g.board[AT(5,9)]=0;g.board[AT(4,0)]=8;g.board[AT(4,9)]=1;g.board[AT(4,5)]=5;
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,5),AT(3,5)));CHECK(pet_p4_xiangqi_is_legal(&g,AT(4,5),AT(4,4)));
  CHECK(pet_p4_xiangqi_in_check(&g,1));CHECK(!pet_p4_xiangqi_is_legal(&g,AT(4,5),AT(4,0)));
  g.board[AT(4,5)]=0;CHECK(pet_p4_xiangqi_in_check(&g,0));CHECK(pet_p4_xiangqi_in_check(&g,1));
  empty(&g);g.board[AT(5,0)]=12;g.board[AT(5,7)]=5;
  CHECK(!pet_p4_xiangqi_is_legal(&g,AT(5,7),AT(4,7)));CHECK(pet_p4_xiangqi_is_legal(&g,AT(5,7),AT(5,6)));
  empty(&g);g.board[AT(5,0)]=13;g.board[AT(5,7)]=5;CHECK(pet_p4_xiangqi_in_check(&g,0));
  CHECK(pet_p4_xiangqi_is_legal(&g,AT(5,7),AT(4,7)));
  g.board[AT(0,8)]=5;CHECK(pet_p4_xiangqi_is_legal(&g,AT(0,8),AT(5,8)));
  empty(&g);g.board[AT(5,0)]=12;g.board[AT(5,7)]=5;g.board[AT(3,8)]=11;
  CHECK(pet_p4_xiangqi_in_check(&g,0));CHECK(!pet_p4_xiangqi_is_legal(&g,AT(5,7),AT(5,6)));
  /* Exact terminal fixtures; both kings remain on the board. */
  empty(&g);g.board[AT(3,0)]=0;g.board[AT(5,9)]=0;g.board[AT(4,0)]=8;g.board[AT(4,9)]=1;g.board[AT(4,5)]=7;
  g.board[AT(0,0)]=5;g.board[AT(0,1)]=5;g.side_to_move=1;
  CHECK(pet_p4_xiangqi_in_check(&g,1));CHECK(!pet_p4_xiangqi_has_legal_move(&g,1));
  g.board[AT(0,1)]=0;CHECK(pet_p4_xiangqi_has_legal_move(&g,1));
  g.board[AT(0,0)]=0;g.board[AT(3,1)]=5;g.board[AT(5,1)]=5;
  CHECK(!pet_p4_xiangqi_in_check(&g,1));CHECK(!pet_p4_xiangqi_has_legal_move(&g,1));
  g.board[AT(0,5)]=14;CHECK(pet_p4_xiangqi_has_legal_move(&g,1));
  puts("rules passed");
}

/* Catches stale guide bits, UI flags corrupting board data, selection walking
 * through illegal destinations, illegal moves mutating history, and undo races. */
static void ui(void) {
  pet_p4_xiangqi_t g;uint8_t cells[90],initial[90];
  pet_p4_xiangqi_init(&g,99,1);CHECK(g.level==1);CHECK(g.board[AT(4,9)]==1);CHECK(g.board[AT(4,0)]==8);
  CHECK(!g.running&&g.status==0);CHECK(pet_p4_xiangqi_command(&g,3));CHECK(g.level==0);
  CHECK(pet_p4_xiangqi_command(&g,4));CHECK(g.level==1);CHECK(pet_p4_xiangqi_ui_score(&g)==16);
  CHECK(pet_p4_xiangqi_command(&g,5));CHECK(g.running&&g.status==1);
  memcpy(initial,g.board,90);g.cursor=AT(1,9);CHECK(pet_p4_xiangqi_command(&g,5));
  CHECK(g.selected==AT(1,9));pet_p4_xiangqi_get_cells(&g,cells);
  unsigned lit=0;for(unsigned i=0;i<90;i++){CHECK((cells[i]&15)==g.board[i]);if(cells[i]&128)lit++;}
  CHECK(lit==2);CHECK(cells[AT(0,7)]&128);CHECK(cells[AT(2,7)]&128);
  CHECK(cells[AT(1,9)]&32);CHECK(pet_p4_xiangqi_command(&g,3));CHECK(g.cursor==AT(0,7)||g.cursor==AT(2,7));
  CHECK(cells[g.cursor]&128);CHECK(pet_p4_xiangqi_command(&g,6));CHECK(g.selected==255);CHECK(!memcmp(initial,g.board,90));
  /* Explicit invalid destination retains selection without changing the board. */
  g.cursor=AT(1,9);CHECK(pet_p4_xiangqi_command(&g,5));g.cursor=AT(1,8);CHECK(pet_p4_xiangqi_command(&g,5));
  CHECK(g.status==5);CHECK(!memcmp(initial,g.board,90));CHECK(!g.ai_pending);
  g.cursor=AT(2,7);CHECK(pet_p4_xiangqi_command(&g,5));CHECK(g.ai_pending&&g.status==3);
  pet_p4_xiangqi_get_cells(&g,cells);CHECK(cells[AT(1,9)]&64);CHECK(cells[AT(2,7)]&64);
  CHECK(pet_p4_xiangqi_command(&g,6));CHECK(!g.ai_pending);CHECK(!memcmp(initial,g.board,90));
  CHECK(!pet_p4_xiangqi_process(&g,256));CHECK(!memcmp(initial,g.board,90));
  /* A rook cannot be guided sideways if it is the sole kings' screen. */
  empty(&g);g.board[AT(3,0)]=0;g.board[AT(5,9)]=0;g.board[AT(4,0)]=8;g.board[AT(4,9)]=1;g.board[AT(4,5)]=5;
  g.cursor=AT(4,5);CHECK(pet_p4_xiangqi_command(&g,5));pet_p4_xiangqi_get_cells(&g,cells);
  CHECK(!(cells[AT(3,5)]&128));CHECK(cells[AT(4,4)]&128);
  /* Capture guide retains the enemy code for a distinct renderer marker. */
  empty(&g);g.board[AT(0,6)]=5;g.board[AT(0,3)]=14;g.cursor=AT(0,6);
  CHECK(pet_p4_xiangqi_command(&g,5));pet_p4_xiangqi_get_cells(&g,cells);CHECK(cells[AT(0,3)]==(128|14));
  /* All seven men have guide sets, with independently counted empty-board
   * destinations as well as consistency with the public legality boundary. */
  static const unsigned origins[7]={86,84,83,67,54,54,38};
  static const unsigned expected[7]={2,1,2,8,17,17,3};
  for(unsigned kind=1;kind<=7;kind++) {
    empty(&g);
    if(kind==4){g.board[AT(5,9)]=0;g.board[AT(4,9)]=1;}
    g.board[origins[kind-1]]=(uint8_t)kind;g.cursor=(uint8_t)origins[kind-1];
    CHECK(pet_p4_xiangqi_command(&g,5));pet_p4_xiangqi_get_cells(&g,cells);lit=0;
    for(unsigned t=0;t<90;t++){CHECK(((cells[t]&128)!=0)==pet_p4_xiangqi_is_legal(&g,g.selected,t));lit+=(cells[t]&128)?1U:0U;}
    CHECK(lit==expected[kind-1]);
  }
  /* Human delivers a genuine mate; no AI can start after the result. */
  empty(&g);g.board[AT(3,0)]=0;g.board[AT(5,9)]=0;g.board[AT(4,0)]=8;g.board[AT(4,9)]=1;g.board[AT(4,5)]=7;
  g.board[AT(0,2)]=5;g.board[AT(1,1)]=5;play(&g,AT(0,2),AT(0,0));CHECK(g.game_over&&g.status==6&&!g.ai_pending);
  CHECK(pet_p4_xiangqi_command(&g,6));CHECK(g.running&&!g.game_over);CHECK(g.board[AT(0,2)]==5);
  /* Human delivers stalemate: same winning result despite no check. */
  empty(&g);g.board[AT(3,0)]=0;g.board[AT(5,9)]=0;g.board[AT(4,0)]=8;g.board[AT(4,9)]=1;g.board[AT(4,5)]=7;
  g.board[AT(3,1)]=5;g.board[AT(5,2)]=5;play(&g,AT(5,2),AT(5,1));CHECK(g.game_over&&g.status==6&&!g.ai_pending);
  CHECK(pet_p4_xiangqi_command(&g,5));CHECK(g.running&&!g.game_over&&g.board[AT(4,0)]==8&&g.side_to_move==0);
  puts("ui passed");
}

static unsigned finish(pet_p4_xiangqi_t *g,unsigned budget) {
  unsigned slices=0;while(g->ai_pending&&slices<100000){pet_p4_xiangqi_process(g,budget);CHECK(g->ai_slice_work<=PET_P4_XIANGQI_SLICE_MAX);slices++;}
  CHECK(!g->ai_pending);return slices;
}
/* Catches blocking full searches, leaking speculative boards into rendering,
 * difficulty settings that do not change search, and submitting stale replies. */
static void ai(void) {
  pet_p4_xiangqi_t g,a,b;uint8_t after_human[90],initial[90];
  unsigned depth[3],work[3];
  for(unsigned level=0;level<3;level++) {
    pet_p4_xiangqi_init(&g,level,44);CHECK(pet_p4_xiangqi_command(&g,5));memcpy(initial,g.board,90);
    play(&g,AT(4,6),AT(4,5));memcpy(after_human,g.board,90);CHECK(g.ai_pending);
    uint32_t revision=g.revision;CHECK(!pet_p4_xiangqi_process(&g,0));CHECK(g.revision==revision);
    CHECK(!pet_p4_xiangqi_process(&g,1));CHECK(g.ai_pending);CHECK(!memcmp(after_human,g.board,90));CHECK(g.ai_slice_work<=1);
    a=g;b=g;unsigned slices=finish(&g,256);CHECK(slices>1);CHECK(g.side_to_move==0&&!pet_p4_xiangqi_in_check(&g,1));
    CHECK(g.board[AT(4,0)]==8);depth[level]=g.ai_completed_depth;work[level]=g.ai_work;
    CHECK(g.last_from<90&&g.last_to<90);CHECK(a.board[g.last_from]>7);CHECK(pet_p4_xiangqi_is_legal(&a,g.last_from,g.last_to));
    finish(&a,7);finish(&b,UINT32_MAX);CHECK(!memcmp(a.board,b.board,90));CHECK(!memcmp(g.board,b.board,90));
    CHECK(pet_p4_xiangqi_command(&g,6));CHECK(!memcmp(initial,g.board,90));CHECK(!g.ai_pending);
    play(&g,AT(4,6),AT(4,5));pet_p4_xiangqi_process(&g,200);CHECK(pet_p4_xiangqi_command(&g,6));
    CHECK(!pet_p4_xiangqi_process(&g,UINT32_MAX));CHECK(!memcmp(initial,g.board,90));
    printf("level %u depth %u work %u slices %u\n",level,depth[level],work[level],slices);
  }
  CHECK(depth[0]>=1);CHECK(depth[1]>=2);CHECK(depth[2]>=3);CHECK(work[0]<work[1]&&work[1]<work[2]);
  /* Black must resolve a rook check rather than make an unrelated move. */
  empty(&g);g.board[AT(4,2)]=12;g.board[AT(4,6)]=5;
  play(&g,AT(4,6),AT(3,6));CHECK(!g.game_over&&g.ai_pending);finish(&g,64);CHECK(!pet_p4_xiangqi_in_check(&g,1));
  /* A one-ply mating reply outranks taking an unrelated pawn. */
  empty(&g);memset(g.board,0,90);g.board[AT(4,9)]=1;g.board[AT(4,0)]=8;g.board[AT(4,4)]=14;
  g.board[AT(0,8)]=12;g.board[AT(1,7)]=12;g.board[AT(8,6)]=7;g.level=0;
  play(&g,AT(8,6),AT(8,5));finish(&g,64);CHECK(g.game_over&&g.status==7);
  /* An interrupted deeper iteration must submit the complete shallower result. */
  pet_p4_xiangqi_init(&a,0,99);CHECK(pet_p4_xiangqi_command(&a,5));play(&a,AT(4,6),AT(4,5));finish(&a,256);
  pet_p4_xiangqi_init(&g,2,99);CHECK(pet_p4_xiangqi_command(&g,5));play(&g,AT(4,6),AT(4,5));
  while(g.ai_completed_depth==0&&g.ai_pending)pet_p4_xiangqi_process(&g,1);
  CHECK(g.ai_pending&&g.ai_completed_depth==1);g.ai_work_limit=g.ai_work+1;finish(&g,256);
  CHECK(g.ai_completed_depth==1);CHECK(!memcmp(a.board,g.board,90));
  /* Even an allowance exhausted before the first legal root is discovered has
   * a legal fallback and cannot turn an unfinished scan into a draw/loss. */
  pet_p4_xiangqi_init(&g,2,99);CHECK(pet_p4_xiangqi_command(&g,5));play(&g,AT(4,6),AT(4,5));a=g;
  pet_p4_xiangqi_process(&g,1);g.ai_work_limit=2;finish(&g,256);
  CHECK(g.ai_completed_depth==0);CHECK(pet_p4_xiangqi_is_legal(&a,g.last_from,g.last_to));CHECK(g.running&&!g.game_over);
  puts("ai passed");
}

/* Fixed-seed legal play walks through changing captures/horse legs/cannon
 * screens instead of only the initial search tree. Every reply stays legal. */
static void games(void) {
  pet_p4_xiangqi_t g,before;uint32_t random=0x12345678U;unsigned replies=0;
  clock_t max_slice=0;
  for(unsigned level=0;level<3;level++) {
    pet_p4_xiangqi_init(&g,level,77);CHECK(pet_p4_xiangqi_command(&g,5));
    for(unsigned round=0;round<16&&!g.game_over;round++) {
      uint8_t from[128],to[128];unsigned count=0;
      for(unsigned f=0;f<90;f++)if(g.board[f]&&g.board[f]<=7)for(unsigned t=0;t<90;t++)if(pet_p4_xiangqi_is_legal(&g,f,t)) {
        CHECK(count<128);from[count]=(uint8_t)f;to[count]=(uint8_t)t;count++;
      }
      CHECK(count>0);random=random*1664525U+1013904223U;unsigned choice=random%count;
      play(&g,from[choice],to[choice]);before=g;
      while(g.ai_pending) {
        clock_t start=clock();bool changed=pet_p4_xiangqi_process(&g,UINT32_MAX);clock_t elapsed=clock()-start;
        if(elapsed>max_slice)max_slice=elapsed;
        CHECK(g.ai_slice_work<=256);
        if(!changed)CHECK(!memcmp(g.board,before.board,90));
      }
      if(g.side_to_move==0) {
        CHECK(pet_p4_xiangqi_is_legal(&before,g.last_from,g.last_to));CHECK(!pet_p4_xiangqi_in_check(&g,1));replies++;
      }
      unsigned kings=0;for(unsigned t=0;t<90;t++){CHECK(g.board[t]<=14);kings+=(g.board[t]==1||g.board[t]==8)?1U:0U;}CHECK(kings==2);
    }
  }
  CHECK(replies>=12);printf("legal-play replies %u; max host slice %.3fms\n",replies,1000.0*(double)max_slice/CLOCKS_PER_SEC);
}

int main(int argc,char **argv) {
  clock_t started=clock();
  if(argc<2||!strcmp(argv[1],"rules"))rules();
  if(argc<2||!strcmp(argv[1],"ui"))ui();
  if(argc<2||!strcmp(argv[1],"ai"))ai();
  if(argc<2||!strcmp(argv[1],"games"))games();
  printf("xiangqi: %u checks passed in %.3fs; state %zu bytes\n",checks,(double)(clock()-started)/CLOCKS_PER_SEC,sizeof(pet_p4_xiangqi_t));
  return 0;
}
