# B站登录态获取教程

## ⚠️ 重要安全警告

**在使用本教程前，请务必注意：**

1. 🔐 **强烈建议使用B站小号**，不要使用你的主账号
   - 登录态（Cookie）相当于账号密码，泄露后可能导致账号被盗
   - 小号即使出问题也不会影响你的主账号

2. 🔑 **SESSDATA 是敏感凭证**
   - 不要分享给任何人
   - 不要硬编码在代码中
   - 不要上传到公开仓库
   - 定期更换（建议每月一次）

3. 🛡️ **本技能仅用于本地处理**
   - 你的SESSDATA不会被发送到任何第三方服务器
   - 仅用于访问B站API获取视频信息

4. ⚡ **风险自负**
   - 使用本功能即表示你了解并接受相关风险
   - 如果账号出现异常，请立即修改密码

---

## 为什么需要登录态？

B站的部分视频需要登录才能查看或下载，为了获取这些视频的内容，需要配置登录态。

**注意：不配置SESSDATA也可以正常使用本技能，仅支持公开内容。**

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

---

## 验证是否生效

运行以下命令检查环境变量是否设置成功：

**Linux/macOS:**
```bash
echo $BILIBILI_SESSDATA
```

**Windows:**
```powershell
echo $env:BILIBILI_SESSDATA
```

如果输出你设置的值，则配置成功。

---

## 常见问题

### Q: SESSDATA 有效期多久？
A: 通常有效期较长，但建议每月更换一次以确保安全。

### Q: 配置后还是无法下载？
A: 
1. 检查环境变量是否正确设置
2. 确认SESSDATA是否过期
3. 尝试重新获取SESSDATA

### Q: 使用小号有什么好处？
A: 避免主账号风险，即使出现问题也不会影响你的主要B站账号。

---

## 安全提示

- ✅ 使用小号而非主账号
- ✅ 定期更换SESSDATA
- ✅ 不要在公共电脑上保存
- ❌ 不要分享给他人
- ❌ 不要上传到公开仓库
- ❌ 不要硬编码在代码中
