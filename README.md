# paper-bilingual-web

将论文 PDF 制作成原文在左、忠实中文译文在右的逐段对照网页的通用 Agent Skills 技能。

## 安装

将仓库克隆到 `~/.agents/skills/`：

```bash
git clone https://github.com/LeoTanFDU/paper-bilingual-web.git ~/.agents/skills/paper-bilingual-web
```

也可下载源码 ZIP，解压后把整个技能文件夹放入该目录，并命名为 `paper-bilingual-web`。Windows 对应 `%USERPROFILE%\.agents\skills\paper-bilingual-web\`。

## 使用

在支持 Agent Skills 的代理工具中提供论文 PDF，并要求使用 `paper-bilingual-web` 将其制作成中英对照网页。支持显式技能引用的工具可直接输入：

```text
用 $paper-bilingual-web 把这些论文制作成中英对照网页。
```

默认逐段忠实翻译，保留原始公式、原图原表和段落布局；图表配中文图注与解释；省略参考文献，保留附录。正文左右等宽，共享页面滚动，不添加额外控件。

辅助脚本依赖 Python 3、`pdfplumber` 和 `Pillow`。数据格式和脚本用法见 [references/blocks.md](references/blocks.md)，完整工作流程见 [SKILL.md](SKILL.md)。输出为可离线打开的静态网页，也可使用当前环境的静态站点工具发布。

![双栏样式预览](assets/reference-preview.png)

## 版本

- `v1.0.0`：原始双栏版本。
