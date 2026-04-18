# B站登录态获取教程

## 为什么需要登录态？

B站的部分视频需要登录才能查看或下载，为了获取这些视频的内容，需要配置登录态。

---

## 方法一：从浏览器获取 SESSDATA（推荐）

### 步骤1：登录B站

在浏览器中访问 https://www.bilibili.com 并登录你的账号。

### 步骤2：打开开发者工具

- **Chrome/Edge**: 按 `F12` 或 `Ctrl+Shift+I` (Mac: `Cmd+Option+I`)
- **Firefox**: 按 `F12`
- **Safari**: 先在菜单栏选择 `开发` → `显示Web检查器`

### 步骤3：找到 Cookie

1. 切换到 **Application** 标签页（或 **存储** 标签页）
2. 左侧菜单找到 **Cookies** → **https://www.bilibili.com**
3. 在右侧列表中找到 **SESSDATA** 这一行

### 步骤4：复制 SESSDATA 值

1. 点击 SESSDATA 行的 **Value** 列
2. 全选并复制这个值（一般是一串类似 `a1b2c3d4%2Ce5f6...` 的字符串）

### 步骤5：配置环境变量

**Linux/macOS:**
```bash
# 临时设置（当前终端有效）
export BILIBILI_SESSDATA="你复制的值"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export BILIBILI_SESSDATA="你复制的值"' >> ~/.bashrc
source ~/.bashrc
```

**Windows:**
```powershell
# 临时设置
$env:BILIBILI_SESSDATA="你复制的值"

# 永久设置
[Environment]::SetEnvironmentVariable("BILIBILI_SESSDATA", "你复制的值", "User")
```

或在 Python 代码中设置：
```python
import os
os.environ['BILIBILI_SESSDATA'] = '你复制的值'
```

---

## 方法二：使用配置文件

在项目目录创建 `.env` 文件：

```bash
# .env 文件内容
BILIBILI_SESSDATA=你复制的值
```

然后在代码中加载：
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 注意事项

⚠️ **安全提醒**：
- SESSDATA 是你的登录凭证，**不要分享给他人**
- 不要在公开的代码仓库中提交这个值
- 定期更换密码会导致 SESSDATA 失效，需要重新获取

⚠️ **有效期**：
- SESSDATA 有一定的有效期（通常30天）
- 过期后需要重新获取

⚠️ **风控**：
- 不要频繁请求，可能触发B站风控
- 建议使用自己的小号，避免主账号风险

---

## 验证配置是否成功

运行测试脚本：

```python
from scripts.bilibili import BilibiliMonitor

monitor = BilibiliMonitor()
info = monitor.get_video_info("BV1GJ411x7h7")  # 测试视频
if info:
    print("✅ B站配置成功")
    print(f"视频标题: {info.get('title')}")
else:
    print("❌ 配置失败，请检查 SESSDATA")
```

---

## 常见问题

### Q: 提示"账号未登录"
A: SESSDATA 可能已过期，请重新获取。

### Q: 提示"访问过于频繁"
A: 触发了风控，请等待一段时间后再试。

### Q: 获取不到 Cookie 列表
A: 确保你已经登录B站，且在 bilibili.com 域名下查看。

---

## 技术原理

SESSDATA 是B站用于识别用户身份的 Cookie，通过在请求中携带这个 Cookie，服务器会认为请求来自已登录用户，从而返回需要登录才能查看的内容。

```
请求示例：
GET /x/web-interface/view?bvid=BV1GJ411x7h7
Cookie: SESSDATA=xxxxx; ...
```

---

*更新时间：2026-04-18*
