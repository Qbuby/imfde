# imfde.ai 登录认证对接指南（GitHub / Google / 微信）

> 登录仅做**身份识别**（展示头像+昵称），不做任何内容限权——访客无需登录也可浏览全部内容。
> 代码已上线（commit `4a34562`），你只需要按本指南创建三个 OAuth 应用并填入环境变量。

---

## 1. 三个应用的回调地址（照抄）

| 渠道 | 授权页入口 | 回调地址（Callback / Redirect URI） |
|---|---|---|
| GitHub | `https://imfde.ai/登录/github` | `https://imfde.ai/登录/github/回调` |
| Google | `https://imfde.ai/登录/google` | `https://imfde.ai/登录/google/回调` |
| 微信 | `https://imfde.ai/登录/wechat` | `https://imfde.ai/登录/wechat/回调` |

> 注意：路径是 `/登录/xxx/回调`（“登录”+“回调”），不是 `/回跳`。

---

## 2. 创建三个 OAuth 应用

### 2.1 GitHub（OAuth App）
1. 打开 https://github.com/settings/developers → **New OAuth App**
2. Homepage URL：`https://imfde.ai`
3. **Authorization callback URL**：粘贴上表 GitHub 那行
4. 创建后拿到 **Client ID** 和 **Client secrets**
5. 授权范围（代码里已固定 `read:user user:email`），无需额外勾选

### 2.2 Google（OAuth 2.0 Client，即 Gmail 登录）
1. 打开 https://console.cloud.google.com/apis/credentials → **Create Credentials** → **OAuth client ID**
2. Application type 选 **Web application**
3. **Authorized redirect URIs**：粘贴上表 Google 那行
4. 创建后拿到 **Client ID** 和 **Client secret**

### 2.3 微信（WeChat 开放平台网站应用）
1. 打开 https://open.weixin.qq.com → 网站应用（网站应用扫码登录，Web 端）
2. 授权回调域：填 `imfde.ai`（注意：微信扫码登录的回调域只填**域名**，不含路径）
3. 应用审核通过后拿到 **AppID** 和 **AppSecret**

---

## 3. 配置 Vercel 环境变量

在 Vercel 项目 → **Settings → Environment Variables** 添加（建议 Production / Preview 都加）：

| 变量名 | 值 | 说明 |
|---|---|---|
| `GITHUB_CLIENT_ID` | `...` | GitHub Client ID |
| `GITHUB_CLIENT_SECRET` | `...` | GitHub Client secret |
| `GOOGLE_CLIENT_ID` | `...` | Google Client ID |
| `GOOGLE_CLIENT_SECRET` | `...` | Google Client secret |
| `WECHAT_APPID` | `...` | 微信 AppID |
| `WECHAT_SECRET` | `...` | 微信 AppSecret |
| `SECRET_KEY` | 随机长字符串 | 会话签名密钥（务必 >= 32 位随机串，泄露会导致会话可伪造） |
| `IMFOAUTHBASE` | `https://imfde.ai` | 回调基址。**生产填 `https://imfde.ai`**；本地开发留空自动取 http://localhost，或按需覆盖 |

> `SECRET_KEY` 可通过 `openssl rand -hex 32` 或任意随机串生成。用 `python -c "import secrets;print(secrets.token_urlsafe(48))"` 也行。

---

## 4. 重新部署并验证

1. 加完变量后**重新部署**（Vercel 环境变量变更需重新部署才生效）
2. 访问 `https://imfde.ai/登录` → 应看到三个按钮（GitHub 登录 / Google 登录 / 微信登录）
3. 点任意一个 → 跳转对应授权页 → 授权后**自动跳回原页面**，导航栏右侧变为「头像 + 昵称」
4. 点击头像 → 退出登录

> 若某渠道按钮未出现：说明对应环境变量未配或为空，该渠道自动隐藏（这是预期行为）。

---

## 5. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 登录页只出现部分按钮 | 对应渠道 env 未填或为空，渠道自动隐藏 |
| 点授权后报「登录状态失效，请重试」 | `oauth_states` 里 state 过期（1 小时）或被清，重走一遍登录即可 |
| 授权后跳回首页而非原页 | `next` 参数被丢弃。确保回调 URL 里 `?next=` 已带上（正常情况会带） |
| `IMFOAUTHBASE` 未设时本地跳 `http://localhost` | 本地开发可用 `IMFOAUTHBASE=http://localhost:8850` 覆盖 |
| 想临时关掉某个渠道 | 删掉对应 env 即可，无需改代码 |

---

## 6. 代码位置（如需改动）

- `portal/site/auth.py`：授权 URL、换 token、拉用户、签名会话 cookie、登录页 HTML
- `portal/site/server.py`：`_handle_auth()`（本地路由）、`auth_link()`（导航入口）、`_CURRENT_COOKIES`
- `api/portal.py`：ASGI 层的 auth 路由 + 把 cookie 传给渲染层
- `vercel.json`：`/登录`、`/退出登录` rewrite（含中文百分号编码版）
- 用户数据表：`users`、`oauth_states`（建在现有 sqlite 库，`auth.ensure_tables` 自动创建）
