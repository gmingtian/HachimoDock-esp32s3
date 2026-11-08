"""Stage public Gomoku metadata without altering the physically accepted package."""
from pathlib import Path
import json
import shutil

root = Path(__file__).resolve().parents[1]
source = root / 'pc/local-clawpkgs/gomoku-a4'
out = root / 'artifacts/gomoku-a4/community'
package = out / 'package'
package.mkdir(parents=True, exist_ok=True)
for name in ['component.json', 'negative-screen.json', 'buttons.json', 'runtime/widget.json', 'share.json', 'assets/board.png']:
    destination = package / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, destination)
for name in ['component.json', 'negative-screen.json', 'runtime/widget.json']:
    path = package / name
    value = json.loads(path.read_text(encoding='utf-8'))
    if name == 'component.json':
        value['author'] = 'gaomt'
    else:
        value['dashboard']['visualSprite'] = 'target'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
metadata = {
    'author': 'gaomt',
    'category': 'game',
    'summary': '离线人机五子棋：15×15 无禁手，你执黑先行。摇杆选点，1键开始/落子/重开，2键悔棋，3键退出。',
    'description': '离线人机五子棋，15×15 棋盘，你执黑先手，设备执白。无禁手，连成五子或以上获胜。\n\n摇杆四向选点；1键开始、落子、重开；2键撤回最近一轮黑白落子，仅支持一级悔棋；3键沿用全局返回，退出到组件列表。橙框为选点，红点标记最后落子，胜局高亮连五。退出并重新打开开始新局，暂不保存未完成棋局。\n\n需要固件支持 gomoku 游戏预设，并配备对应摇杆和按键；当前不支持触屏落子。截图为组件桌面端实际预览。',
    'releaseNotes': 'v1.0.0 首次发布\n\n• 新增离线人机五子棋，15×15 棋盘，你执黑先手，设备执白。\n• 无禁手规则，连成五子或以上获胜。\n• 摇杆四向选点，1键开始/落子/重开，2键悔棋，3键退出。\n• 支持一级悔棋，撤回最近一轮黑白落子。\n• 提供选点光标、最后落子标记和获胜连五高亮。\n• 退出后重新打开开始新局，暂不保存未完成棋局。',
    'sourceUrl': 'https://github.com/YizhengWw/HachimoDock',
    'license': '',
}
(out / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
print(str(package))
