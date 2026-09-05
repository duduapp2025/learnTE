## 个人使用

## 更新：见Economist目录下的download link

### 使用 GitHub Actions

1. Fork 本仓库到你的 GitHub 账号。
2. 打开 Fork 后仓库的 **Actions** 页面，按提示启用工作流。
3. 进入 **Settings → Actions → General → Workflow permissions**，选择 **Read and write permissions** 并保存。
4. 返回 **Actions** 页面，在左侧选择要抓取的杂志工作流。
5. 点击 **Run workflow**，可选填写日期或 TIME 杂志页面 URL；如需替换已有同一期文件，可勾选 **Overwrite existing Release assets**，然后开始运行。

不填写参数时会尝试抓取最新一期。The Economist 和 The New Yorker 的日期可使用 `YYYY-MM-DD` 格式；工作流会分别对齐到最近的周六和周一。TIME 抓取历史期刊时可填写对应的杂志页面 URL。

工作流成功后，PDF 和 EPUB 会出现在你自己 Fork 的 Releases 页面。`INDEX.md` 会在新刊发布后自动更新，也可以通过 **Update magazine index** 工作流手动刷新。

### 在本地运行

本地运行需要安装 [Docker](https://www.docker.com/) 和 [act](https://github.com/nektos/act)，并准备一个对目标仓库具有写入权限的 GitHub Token。

可以在项目根目录创建 `.secrets` 文件：

```text
GITHUB_TOKEN=你的_GitHub_Token
```

然后运行：

```bash
# 抓取最新一期经济学人
./run_local.sh te

# 抓取指定日期
./run_local.sh te 你的_GitHub_Token 2024-05-04

# 其他杂志使用 ny 或 tm
./run_local.sh ny
```

`.secrets`、生成的电子书和本地缓存均已加入 `.gitignore`。




