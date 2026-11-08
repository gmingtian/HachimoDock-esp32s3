/*
 * [Input] Standard-material Xiangqi positions, joystick operations, work slices.
 * [Output] Legal moves, terminal results, guides, and incremental offline AI.
 * [Pos] Portable C11, no ESP-IDF, heap, clock, recursion, or global game state.
 */
#include "pet_p4_xiangqi.h"
#include <string.h>

static int magnitude(int n) { return n < 0 ? -n : n; }
static unsigned piece_side(unsigned p) { return p > 7U ? 1U : 0U; }
static unsigned piece_type(unsigned p) { return (p - 1U) % 7U + 1U; }
static bool palace(int x,int y,unsigned side) {
  return x>=3&&x<=5&&(side ? y>=0&&y<=2 : y>=7&&y<=9);
}

static unsigned between(const uint8_t *b,unsigned from,unsigned to) {
  int fx=(int)(from%9U),fy=(int)(from/9U),tx=(int)(to%9U),ty=(int)(to/9U);
  int dx=tx>fx?1:tx<fx?-1:0,dy=ty>fy?1:ty<fy?-1:0;
  unsigned n=0;
  for(int x=fx+dx,y=fy+dy;x!=tx||y!=ty;x+=dx,y+=dy) if(b[y*9+x])n++;
  return n;
}

/* Attack geometry, including flying kings. It deliberately does not recurse
 * through legal() to decide whether a king is attacked. */
static bool geometry(const uint8_t *b,unsigned from,unsigned to) {
  if(from>=90U||to>=90U||from==to)return false;
  unsigned p=b[from],q=b[to];
  if(p==0U||p>14U||(q&&piece_side(p)==piece_side(q)))return false;
  int fx=(int)(from%9U),fy=(int)(from/9U),tx=(int)(to%9U),ty=(int)(to/9U);
  int dx=tx-fx,dy=ty-fy,ax=magnitude(dx),ay=magnitude(dy);
  unsigned side=piece_side(p),type=piece_type(p);
  switch(type) {
    case 1:
      if(q&&piece_type(q)==1U&&dx==0&&between(b,from,to)==0U)return true;
      return ax+ay==1&&palace(tx,ty,side);
    case 2:return ax==1&&ay==1&&palace(tx,ty,side);
    case 3:return ax==2&&ay==2&&(side?ty<=4:ty>=5)&&b[(fy+dy/2)*9+fx+dx/2]==0;
    case 4:
      if(ax==2&&ay==1)return b[fy*9+fx+dx/2]==0;
      if(ax==1&&ay==2)return b[(fy+dy/2)*9+fx]==0;
      return false;
    case 5:return (dx==0||dy==0)&&between(b,from,to)==0U;
    case 6:return (dx==0||dy==0)&&between(b,from,to)==(q?1U:0U);
    case 7:
      if(dx==0&&dy==(side?1:-1))return true;
      return dy==0&&ax==1&&(side?fy>=5:fy<=4);
    default:return false;
  }
}

static bool checked(const uint8_t *b,unsigned side) {
  unsigned king=side?8U:1U,at=90U;
  for(unsigned i=0;i<90U;i++)if(b[i]==king){at=i;break;}
  if(at==90U)return true;
  for(unsigned i=0;i<90U;i++)if(b[i]&&piece_side(b[i])!=side&&geometry(b,i,at))return true;
  return false;
}

static bool legal(uint8_t *b,unsigned side,unsigned from,unsigned to) {
  if(from>=90U||to>=90U||!b[from]||piece_side(b[from])!=side)return false;
  /* Actual games end at mate; neither the UI nor search removes a king. */
  if(b[to]&&(piece_type(b[to])==1U))return false;
  if(!geometry(b,from,to))return false;
  uint8_t moving=b[from],captured=b[to];b[to]=moving;b[from]=0;
  bool ok=!checked(b,side);b[from]=moving;b[to]=captured;
  return ok;
}

static unsigned candidate_count(unsigned type) {
  static const uint8_t counts[8]={0,4,4,4,8,36,36,3};
  return type<=7U?counts[type]:0U;
}

/* Bounded direct geometry enumerator avoids scanning 90 destinations per man.
 * Out-of-board candidates are consumed, so every search step has finite cost. */
static unsigned candidate_at(unsigned p,unsigned from,unsigned n) {
  static const int8_t dx[4]={0,1,0,-1},dy[4]={-1,0,1,0};
  static const int8_t hx[8]={2,2,-2,-2,1,-1,1,-1};
  static const int8_t hy[8]={1,-1,1,-1,2,2,-2,-2};
  static const int8_t ex[4]={1,1,-1,-1},ey[4]={1,-1,1,-1};
  unsigned type=piece_type(p);int x=(int)(from%9U),y=(int)(from/9U);
  switch(type) {
    case 1:x+=dx[n];y+=dy[n];break;
    case 2:x+=ex[n];y+=ey[n];break;
    case 3:x+=2*ex[n];y+=2*ey[n];break;
    case 4:x+=hx[n];y+=hy[n];break;
    case 5:case 6:x+=dx[n/9U]*(int)(n%9U+1U);y+=dy[n/9U]*(int)(n%9U+1U);break;
    case 7:if(n==0U)y+=piece_side(p)?1:-1;else x+=n==1U?1:-1;break;
    default:return PET_P4_XIANGQI_NONE;
  }
  return x>=0&&x<9&&y>=0&&y<10?(unsigned)(y*9+x):PET_P4_XIANGQI_NONE;
}

static bool any_move(uint8_t *b,unsigned side) {
  for(unsigned f=0;f<90U;f++)if(b[f]&&piece_side(b[f])==side) {
    unsigned n=candidate_count(piece_type(b[f]));
    for(unsigned k=0;k<n;k++)if(legal(b,side,f,candidate_at(b[f],f,k)))return true;
  }
  return false;
}

void pet_p4_xiangqi_init(pet_p4_xiangqi_t *g,unsigned level,uint32_t seed) {
  static const uint8_t back[9]={5,4,3,2,1,2,3,4,5};
  if(!g)return;
  memset(g,0,sizeof(*g));
  g->level=(uint8_t)(level<=2U?level:1U);g->rng=seed?seed:0x7869616eU;
  for(unsigned x=0;x<9U;x++){g->board[x]=(uint8_t)(back[x]+7U);g->board[81U+x]=back[x];}
  g->board[19]=g->board[25]=13;g->board[64]=g->board[70]=6;
  for(unsigned x=0;x<9U;x+=2U){g->board[27U+x]=14;g->board[54U+x]=7;}
  g->cursor=58;g->selected=PET_P4_XIANGQI_NONE;g->last_from=g->last_to=PET_P4_XIANGQI_NONE;
  g->_best_from=g->_best_to=PET_P4_XIANGQI_NONE;g->revision=1;
}
static uint8_t human_status(const pet_p4_xiangqi_t *g) {
  return checked(g->board,0)?PET_P4_XIANGQI_CHECK:PET_P4_XIANGQI_HUMAN;
}

static void apply_game_move(pet_p4_xiangqi_t *g,unsigned from,unsigned to) {
  g->board[to]=g->board[from];g->board[from]=0;
  g->last_from=(uint8_t)from;g->last_to=(uint8_t)to;
  g->selected=PET_P4_XIANGQI_NONE;g->side_to_move^=1U;
  g->_search_started=false;
  uint8_t b[90];memcpy(b,g->board,90);
  if(!any_move(b,g->side_to_move)) {
    g->game_over=true;g->running=false;g->ai_pending=false;
    g->status=g->side_to_move?PET_P4_XIANGQI_RED_WIN:PET_P4_XIANGQI_BLACK_WIN;
  } else if(g->side_to_move) {
    g->ai_pending=true;g->status=PET_P4_XIANGQI_THINKING;
    g->ai_nodes=g->ai_work=g->ai_slice_work=0;g->ai_completed_depth=0;
    g->_best_from=g->_best_to=PET_P4_XIANGQI_NONE;
  } else {
    g->ai_pending=false;g->status=human_status(g);
  }
}

static bool direction(pet_p4_xiangqi_t *g,unsigned op) {
  int x=g->cursor%9U,y=g->cursor/9U;
  if(g->selected==PET_P4_XIANGQI_NONE) {
    if(op==1U)x--;else if(op==2U)x++;else if(op==3U)y--;else y++;
    if(x<0||x>8||y<0||y>9)return false;
    g->cursor=(uint8_t)(y*9+x);g->status=human_status(g);return true;
  }
  uint8_t b[90];memcpy(b,g->board,90);
  int best=100000;unsigned at=PET_P4_XIANGQI_NONE;
  for(unsigned t=0;t<90U;t++) {
    int dx=(int)(t%9U)-x,dy=(int)(t/9U)-y;
    int forward=op==1U?-dx:op==2U?dx:op==3U?-dy:dy;
    if(forward<=0||!legal(b,0,g->selected,t))continue;
    int cross=op<=2U?magnitude(dy):magnitude(dx);
    int cost=(dx*dx+dy*dy)*16+cross*8;
    if(cost<best){best=cost;at=t;}
  }
  if(at>=90U)return false;
  g->cursor=(uint8_t)at;g->status=PET_P4_XIANGQI_SELECTED;return true;
}

bool pet_p4_xiangqi_command(pet_p4_xiangqi_t *g,unsigned op) {
  if(!g||op<1U||op>6U)return false;
  if(op==PET_P4_XIANGQI_UNDO) {
    if(g->selected!=PET_P4_XIANGQI_NONE) {
      g->selected=PET_P4_XIANGQI_NONE;g->status=human_status(g);
    } else if(g->_undo_valid) {
      memcpy(g->board,g->_undo_board,90);g->last_from=g->_undo_last_from;g->last_to=g->_undo_last_to;
      g->cursor=g->_undo_cursor;g->side_to_move=0;g->running=true;g->game_over=false;
      g->ai_pending=false;g->_search_started=false;g->_undo_valid=false;g->status=human_status(g);
    } else return false;
    g->revision++;return true;
  }
  if(!g->running||g->game_over) {
    if(op==PET_P4_XIANGQI_SELECT) {
      unsigned level=g->level;uint32_t seed=g->rng,revision=g->revision;
      pet_p4_xiangqi_init(g,level,seed);g->running=true;g->status=PET_P4_XIANGQI_HUMAN;g->revision=revision+1U;return true;
    }
    if(!g->game_over&&(op==3U||op==4U)) {
      if(op==3U&&g->level>0U)g->level--;
      else if(op==4U&&g->level<2U)g->level++;
      else return false;
      g->revision++;return true;
    }
    return false;
  }
  if(g->ai_pending||g->side_to_move!=0U)return false;
  if(op<=4U) {if(!direction(g,op))return false;g->revision++;return true;}
  if(g->cursor>=90U)return false;
  unsigned p=g->board[g->cursor];
  if(g->selected==g->cursor) {
    g->selected=PET_P4_XIANGQI_NONE;g->status=human_status(g);
  } else if(p&&piece_side(p)==0U) {
    g->selected=g->cursor;g->status=PET_P4_XIANGQI_SELECTED;
  } else if(g->selected<90U&&pet_p4_xiangqi_is_legal(g,g->selected,g->cursor)) {
    memcpy(g->_undo_board,g->board,90);g->_undo_last_from=g->last_from;g->_undo_last_to=g->last_to;
    g->_undo_cursor=g->selected;g->_undo_valid=true;
    apply_game_move(g,g->selected,g->cursor);
  } else g->status=PET_P4_XIANGQI_INVALID;
  g->revision++;return true;
}
#define XQ_INFINITY 32000
#define XQ_MATE 30000

static int piece_value(unsigned p,unsigned at) {
  static const int values[8]={0,0,110,110,320,650,350,85};
  unsigned type=piece_type(p),side=piece_side(p);
  int x=(int)(at%9U),y=(int)(at/9U),advance=side?y:9-y;
  int value=values[type];
  if(type==7U)value+=advance*4+(advance>=5?65:0);
  if(type==4U||type==6U)value+=(4-magnitude(x-4))*3+advance*2;
  return value;
}

static int evaluate(const uint8_t *b,unsigned side) {
  int score=0;
  for(unsigned at=0;at<90U;at++)if(b[at]) {
    int value=piece_value(b[at],at);score+=piece_side(b[at])==side?value:-value;
  }
  return score;
}

static void node_init(pet_p4_xiangqi_t *g,unsigned ply,unsigned remaining,unsigned side,int alpha,int beta) {
  pet_p4_xiangqi_search_frame_t *f=&g->_stack[ply];
  /* Retain fixed move storage, but discard every continuation field. */
  f->alpha=alpha;f->beta=beta;f->best=-XQ_INFINITY;
  f->count=f->next=0;f->scan_from=f->candidate=f->phase=0;
  f->side=(uint8_t)side;f->remaining=(uint8_t)remaining;
  f->best_from=f->best_to=PET_P4_XIANGQI_NONE;g->ai_nodes++;
}

static void iteration_begin(pet_p4_xiangqi_t *g) {
  memcpy(g->_search_board,g->board,90);g->_ply=0;
  node_init(g,0,g->_iteration_depth,1,-XQ_INFINITY,XQ_INFINITY);
}

static void search_begin(pet_p4_xiangqi_t *g) {
  static const uint32_t limits[3]={12000U,90000U,600000U};
  g->ai_target_depth=(uint8_t)(g->level+1U);g->ai_work_limit=limits[g->level];
  g->ai_nodes=g->ai_work=0;g->ai_completed_depth=0;
  g->_iteration_depth=1;g->_best_from=g->_best_to=PET_P4_XIANGQI_NONE;
  g->_search_started=true;iteration_begin(g);
}

/* Returns true when the last completed iteration is ready for submission. */
static bool node_finish(pet_p4_xiangqi_t *g,int value) {
  pet_p4_xiangqi_search_frame_t *f=&g->_stack[g->_ply];
  if(g->_ply==0U) {
    if(f->best_from<90U){g->_best_from=f->best_from;g->_best_to=f->best_to;}
    g->ai_completed_depth=g->_iteration_depth;
    if(g->_iteration_depth>=g->ai_target_depth||value>=XQ_MATE-8)return true;
    g->_iteration_depth++;iteration_begin(g);return false;
  }
  uint8_t from=f->undo_from,to=f->undo_to;
  g->_search_board[from]=f->undo_piece;g->_search_board[to]=f->undo_capture;
  g->_ply--;f=&g->_stack[g->_ply];value=-value;
  if(value>f->best){f->best=value;f->best_from=from;f->best_to=to;}
  if(value>f->alpha)f->alpha=value;
  if(f->alpha>=f->beta)f->next=f->count;
  return false;
}

static void insert_move(pet_p4_xiangqi_search_frame_t *f,const uint8_t *b,unsigned from,unsigned to) {
  /* Valid standard material cannot overflow: 2R*17 + 2C*17 + 2H*8 +
   * 2E*4 + 2A*4 + K*4 + 5P*3 = 119 geometric destinations. */
  if(f->count>=PET_P4_XIANGQI_MAX_MOVES)return;
  int rank=b[to]?piece_value(b[to],to)*16-piece_value(b[from],from):0;
  rank+=piece_value(b[from],to)-piece_value(b[from],from);
  unsigned index=f->count;
  while(index>0U&&rank>f->moves[index-1U].order){f->moves[index]=f->moves[index-1U];index--;}
  f->moves[index].from=(uint8_t)from;f->moves[index].to=(uint8_t)to;f->moves[index].order=(int16_t)rank;f->count++;
}

/* One transition generates one geometric destination or enters/exits one node.
 * The stack and speculative board survive between calls; board[] never changes. */
static bool search_step(pet_p4_xiangqi_t *g) {
  pet_p4_xiangqi_search_frame_t *f=&g->_stack[g->_ply];uint8_t *b=g->_search_board;
  if(f->phase==0U) {
    unsigned from=f->scan_from;
    if(from>=90U) {
      if(f->count==0U)return node_finish(g,-XQ_MATE+(int)g->_ply);
      f->phase=1;return false;
    }
    unsigned p=b[from];
    if(!p||piece_side(p)!=f->side){f->scan_from++;f->candidate=0;return false;}
    unsigned max=candidate_count(piece_type(p));
    if(f->candidate>=max){f->scan_from++;f->candidate=0;return false;}
    unsigned to=candidate_at(p,from,f->candidate++);
    if(!legal(b,f->side,from,to))return false;
    if(f->remaining==0U)return node_finish(g,evaluate(b,f->side));
    if(g->_ply==0U&&g->_best_from>=90U){g->_best_from=(uint8_t)from;g->_best_to=(uint8_t)to;}
    insert_move(f,b,from,to);return false;
  }
  if(f->next>=f->count)return node_finish(g,f->best);
  pet_p4_xiangqi_move_t move=f->moves[f->next++];
  unsigned next=g->_ply+1U;
  node_init(g,next,f->remaining-1U,f->side^1U,-f->beta,-f->alpha);
  pet_p4_xiangqi_search_frame_t *child=&g->_stack[next];
  child->undo_from=move.from;child->undo_to=move.to;
  child->undo_piece=b[move.from];child->undo_capture=b[move.to];
  b[move.to]=b[move.from];b[move.from]=0;g->_ply=(uint8_t)next;
  return false;
}

static void submit_ai(pet_p4_xiangqi_t *g) {
  unsigned from=g->_best_from,to=g->_best_to;
  /* Commands that cancel a search clear ai_pending before this function runs.
   * Revalidation also rejects stale/corrupted speculative output. */
  if(!pet_p4_xiangqi_is_legal(g,from,to)) {
    uint8_t b[90];memcpy(b,g->board,90);from=PET_P4_XIANGQI_NONE;
    for(unsigned f=0;f<90U&&from>=90U;f++)if(b[f]&&piece_side(b[f])==1U) {
      unsigned n=candidate_count(piece_type(b[f]));
      for(unsigned k=0;k<n;k++) {
        unsigned t=candidate_at(b[f],f,k);
        if(legal(b,1,f,t)){from=f;to=t;break;}
      }
    }
  }
  if(from<90U) {
    g->rng=g->rng*1664525U+1013904223U;apply_game_move(g,from,to);
  } else {
    g->ai_pending=false;g->_search_started=false;g->running=false;g->game_over=true;g->status=PET_P4_XIANGQI_RED_WIN;
  }
  g->revision++;
}

bool pet_p4_xiangqi_process(pet_p4_xiangqi_t *g,uint32_t work_budget) {
  if(!g||!g->ai_pending||!g->running||g->game_over||work_budget==0U)return false;
  if(work_budget>PET_P4_XIANGQI_SLICE_MAX)work_budget=PET_P4_XIANGQI_SLICE_MAX;
  if(!g->_search_started)search_begin(g);
  g->ai_slice_work=0;
  for(uint32_t work=0;work<work_budget;work++) {
    if(g->ai_work>=g->ai_work_limit){submit_ai(g);return true;}
    g->ai_work++;g->ai_slice_work++;
    if(search_step(g)){submit_ai(g);return true;}
  }
  return false;
}
void pet_p4_xiangqi_get_cells(const pet_p4_xiangqi_t *g,uint8_t out[90]) {
  if(!out)return;if(!g){memset(out,0,90);return;}memcpy(out,g->board,90);
  if(g->cursor<90U&&!g->game_over)out[g->cursor]|=PET_P4_XIANGQI_CURSOR;
  if(g->last_from<90U)out[g->last_from]|=PET_P4_XIANGQI_LAST;
  if(g->last_to<90U)out[g->last_to]|=PET_P4_XIANGQI_LAST;
  if(g->selected<90U&&g->running&&!g->game_over&&!g->ai_pending) {
    out[g->selected]|=PET_P4_XIANGQI_SELECTION;
    uint8_t b[90];memcpy(b,g->board,90);
    for(unsigned t=0;t<90U;t++)if(legal(b,g->side_to_move,g->selected,t))out[t]|=PET_P4_XIANGQI_LEGAL;
  }
}
int32_t pet_p4_xiangqi_ui_score(const pet_p4_xiangqi_t *g){return g?(int32_t)g->level*16+g->status:0;}
bool pet_p4_xiangqi_is_legal(const pet_p4_xiangqi_t *g,unsigned f,unsigned t){
  if(!g||g->side_to_move>1U)return false;uint8_t b[90];memcpy(b,g->board,90);return legal(b,g->side_to_move,f,t);
}
bool pet_p4_xiangqi_in_check(const pet_p4_xiangqi_t *g,unsigned s){return g&&s<=1U?checked(g->board,s):false;}
bool pet_p4_xiangqi_has_legal_move(const pet_p4_xiangqi_t *g,unsigned s){
  if(!g||s>1U)return false;uint8_t b[90];memcpy(b,g->board,90);return any_move(b,s);
}
