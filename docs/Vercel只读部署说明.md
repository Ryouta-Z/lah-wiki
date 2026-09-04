# LAH Wiki Vercel 只读查询版

`vercel-readonly/` 是可单独上传到 Vercel 的静态查询包。它保留英雄、助手、技能、状态词条、搜索、筛选、排序、英雄与助手标签读取和头像展示；不包含机器人、本机标签管理、写入 API 或任何环境配置。

## 本地构建与预览

在项目根目录执行：

```powershell
python scripts\build_vercel_readonly.py
python -m http.server 8000 --directory vercel-readonly
```

随后在浏览器打开 `http://127.0.0.1:8000/` 仅用于本机预览。生产输出目录是 `vercel-readonly/`；它是纯静态 HTML、CSS、JavaScript 和头像文件，构建后不需要 Python、数据库或本地服务。

## 后续 Vercel 设置

本次不执行 Vercel 部署。之后创建项目时，将根目录设为 `vercel-readonly`，选择静态站点（Framework Preset: Other），不填写 Build Command，Output Directory 使用 `.`。

只能上传或连接 `vercel-readonly/`，不能把当前仓库根目录作为公开部署根目录：根目录包含本地机器人、维护脚本、缓存资料，并且现有 `.env` 含 OneBot 访问令牌配置。该文件和现有本机机器人文档都不会进入只读包。

## 更新流程

先在本地按现有流程更新游戏数据或公共英雄/助手标签，再重新运行只读包构建命令。构建脚本只读取当前 `data/quickref_catalog.json` 和被引用头像，不会改写它们，也不会启动标签管理服务。

构建脚本仅使用 Python 标准库和现有静态页生成器，要求 Python 3.12 或更高。本机已使用 `python`（3.14）完成构建与检查；不依赖当前 `.venv`。
