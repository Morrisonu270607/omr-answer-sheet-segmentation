# GitHub 登录与上传教程（最短路径）

> 下面的操作只在浏览器里打开 **https://github.com** 完成。不要把密码、二次验证码发给我，也不要发给任何“代传”的人。

## 1. 先弄清三个东西

登录 GitHub 需要：

1. **用户名**（Username），例如 `zhangsan`，不是邮箱；
2. **密码**；
3. 如果开了**双重验证（2FA）**，还需要手机验证器里的 6 位动态码或备用码。

登录后如果不知道用户名：点右上角头像 → **Your profile**，浏览器地址栏 `github.com/` 后面的那一段就是用户名。也可以点头像旁边的小箭头查看。

如果你买的是现成账号，先向卖家确认：**用户名、登录邮箱、邮箱是否还能收信、是否开了 2FA、有没有备用码**。没有邮箱控制权的账号不要用，后面找不回。

## 2. 登录

1. 打开 <https://github.com/login>。
2. 在 “Username or email address” 填用户名或邮箱。
3. 在 “Password” 填密码，点 **Sign in**。
4. 如果出现 **Authentication code**：打开手机上的验证器（Google Authenticator / Microsoft Authenticator / 1Password 等），输入 6 位码；没有验证器就点 “Use a recovery code” 用备用码。
5. 如果出现 **Device verification**：去邮箱收 6 位验证码，填进去。
6. 如果提示密码错误：点 “Forgot password?”，用注册邮箱重置。邮箱不是你的，就只能找卖家，别继续往里传东西。

登录成功后，点右上角头像，能看到 **Your profile**、**Settings**，说明成功了。

## 3. 登录后先做 4 件事（强烈建议）

1. **改密码**：头像 → Settings → Password and authentication → Change password。
2. **确认邮箱**：Settings → Emails，确保主邮箱能收信；没验证的点 Verify。
3. **开 2FA**：Settings → Password and authentication → Two-factor authentication → Enable。保存好备用码。
4. **改用户名（可选）**：Settings → Account → Change username。用户名会进入主页和仓库链接，改完记下来。

如果你不想折腾买的账号，也可以直接用邮箱注册一个新账号：<https://github.com/signup>。对课程作业来说，新账号完全够用。

## 4. 创建仓库

1. 登录后点右上角 **+** → **New repository**。
2. **Repository name** 填：

   ```text
   omr-answer-sheet-segmentation
   ```

3. 选 **Public**。
4. 下面的 “Add a README file / Add .gitignore / Choose a license” **都不要勾**，因为项目里已经有了。
5. 点 **Create repository**。

创建成功后，浏览器地址就是：

```text
https://github.com/你的用户名/omr-answer-sheet-segmentation
```

把“你的用户名”记下来，后面要填进报告。

## 5. 上传工程（推荐 GitHub Desktop）

网页上传也能用，但文件多的时候容易漏。最稳的是 GitHub Desktop：

1. 打开 <https://desktop.github.com/>，下载安装。
2. 打开 GitHub Desktop → **Sign in to GitHub.com**，用同一个账号登录。
3. 菜单 **File → Add local repository**，选择你电脑上的整个项目文件夹：

   ```text
   omr-answer-sheet-segmentation
   ```

4. 如果提示 “not a Git repository”，点 **create a repository**，然后点 **Create repository**。
5. 点右上角 **Publish repository**。
6. Name 保持 `omr-answer-sheet-segmentation`，**取消勾选 “Keep this code private”**，点 **Publish repository**。

等几十秒，刷新网页仓库，能看到 `README.md`、`src/`、`data/` 就成功了。

### 如果不想装软件：网页上传

1. 打开刚创建的仓库页面。
2. 点 **Add file → Upload files**。
3. 把项目文件夹里的**内容**（不是外层文件夹）拖进去：`README.md`、`src`、`data`、`docs`、`results`、`report`、`requirements.txt` 等。
4. 下方 Commit message 填 `Add OMR course design project`，点 **Commit changes**。
5. 如果某个文件夹没传上去，点 **Add file → Create new file**，在文件名里输入 `src/omr/config.py` 这种带斜杠的路径，再把内容粘进去。文件多时还是建议 GitHub Desktop。

## 6. 把报告里的占位符换成你的信息

工程和报告里现在用 `×××` 代替个人信息：

- 报告封面：`××大学`、`××学院`、`××专业`、`××班`、`××学号`、`××姓名`；
- 报告第 1 节：`https://github.com/×××/omr-answer-sheet-segmentation`；
- `README.md` 第一行的 GitHub 链接。

用 Word 打开报告，逐个选中 `×××` 替换成你的信息；GitHub 链接里的 `×××` 换成你的用户名。改完保存。

> 如果你把“学院/专业/班级/学号/姓名/GitHub 用户名”发我，我可以直接帮你生成填好的版本。

## 7. 拿到可提交的链接

仓库页面地址就是提交链接，格式：

```text
https://github.com/你的用户名/omr-answer-sheet-segmentation
```

提交前检查：

- [ ] 网页能打开，未登录也能看到 README 和代码；
- [ ] `report/图像处理课程设计报告.docx` 能下载；
- [ ] 报告封面和 GitHub 链接里的 `×××` 已替换；
- [ ] 没有把密码、验证码、身份证号传到仓库；
- [ ] 仓库是 Public。

## 8. 常见问题

**Q：登录时一直转圈/打不开？**
换 Edge/Chrome，关掉代理再试；或手机流量开热点。GitHub 在国内偶尔不稳定。

**Q：要 2FA 但没有验证器？**
找卖家要备用码（recovery code）；都没有就点 “Can't access your two-factor authentication?” 走邮箱验证。邮箱不是你的，基本救不回来。

**Q：上传时提示文件太大？**
这个工程里单张图几百 KB，不会超。若把整个 `omr-answer-sheet-segmentation.zip` 传上去，先解压，不要传 zip。

**Q：网页上传后文件夹是空的？**
GitHub 网页对空文件夹不友好。先确认本地文件夹里有文件，再用 GitHub Desktop 上传。

**Q：`git` 命令找不到？**
这个教程用 GitHub Desktop，不需要装 Git 命令行。想用命令行再另装 Git，并配置 Personal Access Token，不要用登录密码 push。
