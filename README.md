# XLIFF AI Assistant (傻瓜式运行指南)

这是一个利用 AI 帮助翻译 XLIFF 文件（memoQ/Trados 导出格式）的工具。它能保护文件中的格式标签，防止 AI 破坏文件结构。

---

## 🚀 第一次安装 (只需要做一次)

### 1. 安装环境依赖
确保你已经安装了 Python 和 Node.js。

### 2. 初始化项目
打开命令行 (PowerShell 或 CMD)，复制以下命令并回车：

```powershell
# 进入项目目录 (如果你还没在里面)
cd .gemini\antigravity\scratch\xliff_ai_assistant

# 1. 安装 Python 后端库
pip install lxml fastapi uvicorn python-multipart

# 2. 安装前端库
cd web
npm install
cd ..
```

---

## ▶️ 怎么运行 (每次使用时)

你需要打开 **两个** 黑色命令行窗口。

### 第 1 个窗口：启动后端服务 (Backend)

复制粘贴：
```powershell
cd .gemini\antigravity\scratch\xliff_ai_assistant
python server/app.py
```
*当看到 `Uvicorn running on http://0.0.0.0:8000` 时，说明后端启动成功。**不要关闭这个窗口**。*

### 第 2 个窗口：启动网页界面 (Frontend)

复制粘贴：
```powershell
cd .gemini\antigravity\scratch\xliff_ai_assistant\web
npm run dev
```
*当看到 `Local: http://localhost:5173` 时，说明前端启动成功。*

---

## 🌐 开始使用

打开浏览器 (Chrome/Edge)，访问：
**[http://localhost:5173](http://localhost:5173)**

1.  把你的 `.xlf` 文件拖进去。
2.  点击 **"Translate All"** 等待 AI 翻译。
3.  翻译完后，点击 **"Export XLIFF"** 下载文件。
4.  把下载的文件导回 memoQ/Trados 即可。

---

## 🛠️ 常见问题

**Q: 运行 `python server/app.py` 报错找不到文件？**
A: 请确保你先执行了 `cd` 命令进入了正确的文件夹。看上面的路径。

**Q: 网页打不开？**
A: 请检查两个黑色窗口是不是都开着，并且没有报错。

**Q: 翻译是假的？**
A: 目前使用的是演示模式 (Mock AI)，为了省钱不消耗 Token。它会把原文复制并在前面加 `[Zh]`。
如果要接入真实 AI，请联系开发修改 `ai/client.py`。
