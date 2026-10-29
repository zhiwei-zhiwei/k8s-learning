# 第 0 课：准备工作

## 目标

把 `kube-toy` 的第一版（只有 `GET /`）写出来，在本机跑通，打成镜像 `kube-toy:v1`，再用 `kind load` 放进 `learn` 集群。

## 概念（用我自己的话写）

- 起始准备，创建一个learn cluster - 启动了一个容器/节点叫做learn-control-plane。这是通过kind create cluster --name learn --config kind/cluster.yaml启动起来的，容器/节点命名规则是"cluster name"-"role name"。这句同时在容器来把k8s启动起来，让他变成一台机器。

- 然后写了main.py - 主要的开发部分

- 再通过docker把这个main.py打包成镜像 - k8s只认image

- 最后再把这个image通过“kind load”送到节点上 - 节点就是创建的cluster

## 我的预测 → 实际结果

| 操作                                      | 我预测                        | 实际                                 | 为什么                                                      |
| ----------------------------------------- | ----------------------------- | ------------------------------------ | ----------------------------------------------------------- |
| 建好集群后 `docker ps` 会多出什么         | （没写预测）                  | 多了一个容器 `learn-control-plane`   | kind 用一个 Docker 容器当一台节点                           |
| 在 Mac 上跑，`pod` 是什么                 | 我电脑的名字？                | `MacBookPro.home.local` ✅           | 程序跑在 Mac 上，拿到的是 Mac 的名字                        |
| 在 Mac 上跑，`version` 是什么             | `0`                           | `dev` ❌                             | 没设置 `APP_VERSION`，用了默认值 `"dev"`                    |
| 在容器里跑，`pod` 是什么                  | `kube-toy`                    | `63a3b70dc360` ❌                    | 没给容器起名字，hostname 默认是容器 ID；`kube-toy` 是镜像名 |
| `kind load` 之前，集群能用 Mac 上的镜像吗 | 不可以，image 还没被送到 node | 不能 ✅（`not yet present on node`） | 节点有自己的镜像仓库，看不到 Mac 上 Docker 里的镜像         |

## 命令记录

```bash
# 1. replace the old cluster with "learn"
kind delete cluster --name lexisai
kind create cluster --name learn --config kind/cluster.yaml
kubectl config current-context        # kind-learn
kubectl get nodes
docker ps

# 2. run the app on the Mac
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cd app && uvicorn main:app --port 8000
curl localhost:8000/

# 3. build the image and run it with Docker
docker build -t kube-toy:v1 app
docker run --rm -p 8000:8000 -e APP_VERSION=v1 kube-toy:v1
curl localhost:8000/

# 4. put the image on the node
docker exec learn-control-plane crictl images | grep kube-toy
kind load docker-image kube-toy:v1 --name learn #仅仅是吧这个image复制到这个node之中，让这个node能够看到这个image，还没有启动任何容器
docker exec learn-control-plane crictl images | grep kube-toy
```

## 踩坑记录（每个坑都标上类别：K8s / shell·工具 / 程序）

| 现象                                                                 | 原因                                                                         | 类别       |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------- |
| `docker run` 后马上退出，报 `Name or service not known`，curl 连不上 | Dockerfile 里把 `--host 0.0.0.0` 写成了 `0,0,0,0`；改完要重新 `docker build` | 程序本身   |
| curl 的结果最后多了一个 `%`                                          | 输出结尾没有换行，zsh 补了一个 `%` 做标记，不是程序输出的                    | shell·工具 |
| `docker ps` 里找不到 `63a3b70dc360`                                  | 按了 `Ctrl+C` 容器就停了，加了 `--rm` 停了就自动删掉                         | shell·工具 |
| `grep: exec: No such file or directory` 一串报错                     | 同一条命令粘贴了两次连成一行，`grep` 把后面的词当成了文件名                  | shell·工具 |

## 自测题和我的回答

### 1. 在 Mac 上执行 docker run 跑容器，和让 K8s 集群跑容器，镜像是从哪里来的？为什么需要 kind load 这一步？

答：镜像是一开始使用“docker build -t kube-toy:v1 app”构建的，在本地进行了测试能够打通。k8s跑的容器是来自于kindest/node(cluster.yaml)。因为kind load只认识image，不接受.py.

Claude判断答案以及解释：**对了一半。**

- ✅ 镜像是用 `docker build` 做出来的，这一点对。
- ❌ `kindest/node` 是**节点本身**的镜像，也就是那台"机器"是用什么做的，不是你程序的镜像。
- ❌ 需要 `kind load` 的原因不是"只认 image、不认 .py"。真正的原因是：节点是**另一台机器**，有**自己的镜像仓库**，看不到你 Mac 上 Docker 里的镜像。
- 一句话：`docker run` 用的是 Mac 上 Docker 里的镜像；K8s 用的是**节点自己仓库**里的镜像。`kind load` 就是把镜像从 Mac 复制到节点上。

更新答案：k8s跑的是k8s自己的仓库中的image，docker run怕的是mac上创建的image，k8s看不到mac上的image，所欲需要kind load，吧mac上的image复制到k8s的节点(learn)上。


### 2. 同一个程序，在 Mac 上跑时 pod 是 MacBookPro.home.local，在容器里跑时变成了 63a3b70dc360。为什么会不一样？

答：因为在Mac上跑时，我们给他命名为socket.gethostname() - 拿到的就是电脑的名字；我没给容器起名字，它的 hostname 默认就是容器 ID。

Claude判断答案以及解释：**基本正确。**

- ✅ 容器的 hostname 默认是容器 ID，对。
- 小修正：不是"我们给它命名为 `socket.gethostname()`"。`socket.gethostname()` 的意思是**问一句"我现在在哪台机器上"**。代码一行没变，只是程序**跑的地方**变了，答案也就跟着变了：在 Mac 上就是 Mac 的名字，在容器里就是容器的名字。

更新答案：简单来说一个程序在不同的地方跑就会有不同的名称，在本地电脑直接用 uvicorn 跑的程序就是本地电脑名称，容器里用image跑就是容器的名称，这里会用id来替代。

## 对应 LexisAI 的哪一行（文件:行号）
