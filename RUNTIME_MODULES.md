# 运行时模块系统

## 能力说明

- 支持 ZIP 安装用户自定义模块
- 支持运行时动态加载、卸载、重载，无需重启后端
- 模块信息持久化保存到 `system_runtime_module`
- 模块以独立 Python 包形式解耦，按需引入
- 提供统一执行入口：`/runtime-module/execute/{module_code}/{route_path}`
- 内置抽奖示例模块 `lottery_demo`

## 模块目录结构

```text
your_module/
  manifest.json
  __init__.py
  module.py
```

## manifest.json 示例

```json
{
  "code": "lottery_demo",
  "name": "抽奖示例模块",
  "version": "1.0.0",
  "description": "一个可热插拔的抽奖示例模块",
  "author": "system",
  "entry_module": "module",
  "class_name": "Module",
  "config": {
    "default_winner_count": 1
  }
}
```

## 模块代码示例

```python
from runtime_modules.base import RuntimeModuleBase, RuntimeModuleRoute


class Module(RuntimeModuleBase):
    def get_routes(self):
        return [
            RuntimeModuleRoute(path="/meta", methods=["GET"], handler="meta"),
            RuntimeModuleRoute(path="/draw", methods=["POST"], handler="draw"),
        ]

    async def meta(self, request):
        return {"name": self.context.name}

    async def draw(self, request):
        payload = await request.json()
        return {"payload": payload}
```

## 接口清单

- `GET /runtime-module/list`
- `GET /runtime-module/info/{module_code}`
- `GET /runtime-module/examples`
- `POST /runtime-module/install/upload`
- `POST /runtime-module/install/example/{example_code}`
- `POST /runtime-module/load/{module_code}`
- `POST /runtime-module/unload/{module_code}`
- `POST /runtime-module/reload/{module_code}`
- `PUT /runtime-module/config/{module_code}`
- `DELETE /runtime-module/uninstall/{module_code}`
- `GET|POST|PUT|PATCH|DELETE /runtime-module/execute/{module_code}/{route_path}`

## 快速体验

1. 重启后端，让 `system_runtime_module` 表自动创建。
2. 调用 `POST /runtime-module/install/example/lottery_demo` 安装抽奖示例模块。
3. 调用 `GET /runtime-module/execute/lottery_demo/meta` 查看模块说明。
4. 调用 `POST /runtime-module/execute/lottery_demo/draw`，请求体：

```json
{
  "participants": ["张三", "李四", "王五", "赵六"],
  "winner_count": 2
}
```

## 说明

- 当前这套实现以“后端热插拔模块”为核心。
- 如果后续你要做完整前端可视化模块市场，可以直接基于 `manifest` 字段扩展菜单、前端资源包和配置面板。
