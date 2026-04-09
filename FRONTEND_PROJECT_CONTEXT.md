# Frontend Project Context

适用项目：`E:\test\art-design-pro-main`

这份文档用于快速恢复前端项目上下文，减少每次重新翻文件的时间。当前前端与本仓库后端 `E:\test\fastapi-admin` 配套使用。

## 1. 项目定位

- 技术栈：`Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + TailwindCSS`
- 权限模式：当前 `.env` 中 `VITE_ACCESS_MODE = backend`，以“后端返回菜单 + Casbin 权限”作为主模式
- 富文本编辑器：项目已安装 `@wangeditor/editor` 与 `@wangeditor/editor-for-vue`
- 请求层：统一走 `src/utils/http/index.ts`
- 动态菜单：由后端 `/menus/list` 返回，前端再转换成路由

## 2. 启动与环境

关键文件：

- `E:\test\art-design-pro-main\package.json`
- `E:\test\art-design-pro-main\.env`

常用命令：

```bash
pnpm dev
pnpm build
pnpm lint
```

当前环境要点：

- `VITE_PORT = 3006`
- `VITE_BASE_URL = /`
- `VITE_ACCESS_MODE = backend`
- `VITE_WITH_CREDENTIALS = false`

注意：

- 前端请求基地址来自 `import.meta.env.VITE_API_URL`
- axios 会自动带上 `Authorization` 请求头，token 来自 `userStore.accessToken`

## 3. 关键目录速查

### 页面

- `src/views/system/user`
- `src/views/system/role`
- `src/views/system/department`
- `src/views/system/permission`
- `src/views/system/menu`

### 接口封装

- `src/api/auth.ts`
- `src/api/user.ts`
- `src/api/role.ts`
- `src/api/department.ts`
- `src/api/menu.ts`
- `src/api/permission.ts`

### 路由

- `src/router/index.ts`
- `src/router/routes/staticRoutes.ts`
- `src/router/routes/asyncRoutes.ts`
- `src/router/modules/*.ts`
- `src/router/core/*`

### 状态与权限

- `src/store/modules/user.ts`
- `src/store/modules/menu.ts`
- `src/hooks/core/usePermission.ts`
- `src/directives/core/auth.ts`

### 通用组件

- `src/components/core/forms/art-wang-editor/index.vue`

## 4. 当前菜单与权限链路

后端模式下，菜单和权限的大致链路如下：

1. 登录成功后，用户信息进入 `src/store/modules/user.ts`
2. `userStore.info` 中会保存：
   - `permission_marks`
   - `menus`
   - `buttons`
   - `apis`
   - `casbin_roles`
3. 菜单由 `src/router/core/MenuProcessor.ts` 调用 `fetchGetMenuList()` 从后端获取
4. 后端返回的菜单再经过：
   - `MenuProcessor`
   - `RouteTransformer`
   - `ComponentLoader`
5. 最终把后端 `component` 字段映射为 `src/views/**` 下的实际页面组件

### 动态组件映射规则

`src/router/core/ComponentLoader.ts` 会按下面两种路径查找页面：

```ts
../../views${componentPath}.vue
../../views${componentPath}/index.vue
```

例如：

- 后端返回 `component: /system/user`
- 实际会命中 `src/views/system/user/index.vue`

所以后端菜单表里的 `component` 字段必须与 `src/views` 下路径严格对应。

## 5. 按钮权限怎么生效

按钮权限不是只靠页面写死，而是和后端权限标识联动：

- 页面里通过 `v-auth="'user:btn:addUser'"` 这种方式控制按钮显示
- `v-auth` 依赖 `userStore.info.permission_marks`
- `permission_marks` 来自后端 `/auth/info`
- 后端权限数据主要来自：
  - `system_permission`
  - `casbin_rule`

相关文件：

- `src/directives/core/auth.ts`
- `src/hooks/core/usePermission.ts`

结论：

- 新模块如果要做按钮鉴权，前端要写 `v-auth`
- 后端要同时补菜单权限、按钮权限、API 权限以及角色授权数据

## 6. 菜单页面和权限页面的区别

这套项目里有两类相近但用途不同的页面：

### 菜单管理页

文件：

- `src/views/system/menu/index.vue`

用途：

- 更偏展示当前路由菜单结构
- 和前端路由配置、按钮元数据有关

### 权限管理页

文件：

- `src/views/system/permission/index.vue`

用途：

- 更贴近后端 `system_permission`
- 可配置菜单、按钮、API 权限
- 当前动态菜单主要应以这里维护的数据为准

如果新增业务模块，优先考虑和“权限管理页”这套后端权限模型对齐。

## 7. 请求层约定

统一请求文件：

- `src/utils/http/index.ts`

约定：

- 成功不是看 HTTP 200，而是看返回体 `code === 200`
- `request.get/post/put/del` 最终返回的是 `res.data.data`
- 401 会触发统一登出
- `POST/PUT` 如果只传 `params`，请求层会自动转到 `data`

所以新增接口封装时保持现有风格即可，例如：

```ts
return request.get({
  url: '/article/list',
  params
})
```

## 8. 富文本编辑器现状

项目里已经有可直接复用的封装组件：

- `src/components/core/forms/art-wang-editor/index.vue`

它已经做了：

- `wangEditor` 基础封装
- 图片上传配置
- token 注入
- 工具栏配置透传

默认图片上传地址：

```txt
${VITE_API_URL}/api/common/upload/wangeditor
```

这意味着如果要做文章管理：

- 前端可直接复用 `art-wang-editor`
- 后端需要提供 `/api/common/upload/wangeditor` 对应接口

## 9. 新增业务模块时的最小接入清单

以“文章管理”为例，通常需要同时改这些地方：

### 前端

- `src/api/article.ts`
- `src/views/article/index.vue` 或 `src/views/content/article/index.vue`
- 如有编辑抽屉/详情页，再新增对应子组件

如果菜单走后端动态配置：

- 前端不一定非要改 `src/router/modules/*.ts`
- 但页面文件路径必须和后端 `component` 字段一致

如果需要按钮权限：

- 页面按钮增加 `v-auth`
- 后端补对应 `authMark`

### 后端

- 新模型：文章表
- 新接口：列表、详情、新增、修改、删除、发布/下线
- 新路由注册
- 如需富文本图片：补上传接口
- 在 `system_permission` 中补：
  - 菜单权限
  - 按钮权限
  - API 权限

## 10. 和当前后端项目的耦合点

前后端当前是明显配套设计，核心耦合点如下：

- 登录与用户信息：`/auth/login`、`/auth/info`
- 动态菜单：`/menus/list`
- 权限树与按钮/API 权限：`/permission/*`
- 角色授权：`/role/updatePermission/{role_id}`

这意味着新业务模块如果只写前端页面、不补后端权限，通常会出现：

- 菜单不显示
- 按钮不显示
- 接口调用 401/无权限
- 角色无法配置访问范围

## 11. 后续优先建议

如果后面开始做“文章管理”，建议按下面顺序：

1. 后端先补文章表和 CRUD
2. 后端补发布状态字段与发布接口
3. 后端补图片上传接口，兼容 `art-wang-editor`
4. 前端补 `src/api/article.ts`
5. 前端补文章列表页和编辑页
6. 最后在权限管理里补菜单、按钮、API 权限

## 12. 常看文件清单

以后接手这个前端，优先看下面这些文件就够了：

- `E:\test\art-design-pro-main\package.json`
- `E:\test\art-design-pro-main\.env`
- `E:\test\art-design-pro-main\src\utils\http\index.ts`
- `E:\test\art-design-pro-main\src\store\modules\user.ts`
- `E:\test\art-design-pro-main\src\hooks\core\usePermission.ts`
- `E:\test\art-design-pro-main\src\router\core\MenuProcessor.ts`
- `E:\test\art-design-pro-main\src\router\core\RouteTransformer.ts`
- `E:\test\art-design-pro-main\src\router\core\ComponentLoader.ts`
- `E:\test\art-design-pro-main\src\api\permission.ts`
- `E:\test\art-design-pro-main\src\views\system\permission\index.vue`
- `E:\test\art-design-pro-main\src\components\core\forms\art-wang-editor\index.vue`

## 13. 一句话总结

这个前端不是“页面写完就行”的结构，而是“页面 + 动态菜单 + Casbin 权限 + 后端返回用户权限”联动的后台系统。以后新增模块时，优先先想清楚页面路径、接口、按钮权限标识和后端权限数据怎么一起落地。
