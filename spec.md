# K8s 从零练习项目：spec

> 一句话：用一个自己写的小 FastAPI 程序（`kube-toy`），每次只学一个 Kubernetes 概念，手写原始 YAML，先预测结果再动手，2 周学完基础。最后逐行讲懂 LexisAI 的 Helm chart，然后回去做 LX-2。

---

## 1. 为什么要做这个项目

在 LexisAI 上做 LX-1 的时候，K8s 本身的难度和 LexisAI 自己的复杂度（SSE、Docling 吃 3 GB 内存、SQLite 单写入者、build 时写死的前端地址）缠在了一起，再加上 shell、时序这些不属于 K8s 的坑，最后很难分清「哪些是 K8s 的知识」。

这个项目把它们拆开：

- **练习程序很简单，而且完全由你控制。** 想让它变慢、生病、吃内存、写文件，都只是调一个接口的事。
- **每节课只引入一个新概念。** 一节课里不会同时出现两样没见过的东西。
- **Helm 放到第 9 课。** 在那之前只手写原始 YAML，先弄懂 K8s 本身的语法和语义，再学模板。
- **每遇到一个问题，都先标清楚它属于哪一类。** 是 K8s 的知识、shell 或工具的细节，还是程序本身的问题。

### 学完以后的目标

1. LexisAI 的 `deploy/` 目录（chart、kind 配置、device plugin、CI 里的 `k8s-smoke`），**每一行都能用自己的话讲清楚**。
2. 部署出了问题，能自己用 `get` / `describe` / `logs` / `events` 查到原因，不需要别人帮忙。
3. 已经在 Jetson 上跑通过「申请 GPU 的服务，被 kind 里的服务跨机器调用」。回去做 LX-2 时，这就是熟悉的操作。

### 不做的事

- 不碰 LexisAI 的仓库和集群。
- 不学云上的 K8s（EKS）和 Terraform。LX-3 已经降为选做。
- 不追求面面俱到。StatefulSet、Operator、RBAC 细节、网络插件、Service Mesh 都不在这次的范围内，以后需要时再学。

---

## 2. 环境

| 项目     | 情况                                                                                                                                          | 注意                                                                                                                                                                                                    |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 开发机   | M1 Pro Mac，16 GB 内存，Docker Desktop 只分到 **4 GB**                                                                                        | 所有内存上限都要设得很小（几十到几百 MiB）；OOM 实验用 100–200 MiB 的上限来做                                                                                                                           |
| 本地集群 | kind，新建一个叫 `learn` 的集群                                                                                                               | **先删掉 LexisAI 的集群**：`kind delete cluster --name lexisai`。原因有两个：它也占着 80/443 端口，两个集群同时开会把 4 GB 内存吃光。LexisAI 的 chart 都在 git 里，随时可以重建，只是里面上传的文档会丢 |
| Jetson   | Orin Nano 8 GB，k3s v1.36，已装 NVIDIA device plugin，节点上有 `nvidia.com/gpu: 1`；镜像 `nvcr.io/nvidia/pytorch:24.12-py3-igpu` 已缓存在本机 | 只能通过 Tailscale 访问：`ssh 100.64.184.113`。sudo 需要密码，所以用到 sudo 的步骤由你自己执行。Traefik 和 ServiceLB 已经关掉了（内核缺 `nft_compat`），对外暴露服务用 NodePort                         |
| 工具     | kubectl、kind、helm、docker、gh 都已安装                                                                                                      |                                                                                                                                                                                                         |

---

## 3. 练习程序 `kube-toy`

一个很小的 FastAPI 程序。**由你自己来写，而且是一课一课地长出来**：每节课只加那节课需要的接口，课程开始时它只有一个 `/`。

### 最终的接口（每个接口在第几课加上）

| 接口                                      | 作用                                                                                           | 加入的课 | 用来演示                                           |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------- |
| `GET /`                                   | 返回 `{"pod": <hostname>, "version": APP_VERSION}`                                             | 0        | 请求被转给了哪个 Pod、跑的是哪个版本               |
| `GET /config`                             | 显示读到的配置：`GREETING`、`API_TOKEN` 的长度和最后一个字符的 `repr`。**绝不显示 token 本身** | 4        | ConfigMap、Secret，以及「末尾的换行符」这个坑      |
| `GET/POST /notes`                         | 在 `DATA_DIR/notes.txt` 里追加和读取一行文字                                                   | 5        | Pod 重建以后数据还在不在                           |
| `GET /health`                             | liveness 检查用；「生病」以后返回 500                                                          | 6        | liveness 失败 → 重启                               |
| `GET /ready`                              | readiness 检查用；启动后的前 `STARTUP_SECONDS` 秒，以及被标记为「暂停接客」时返回 503          | 6        | readiness 失败 → 不再转发请求，但不重启            |
| `POST /admin/sick`、`POST /admin/unready` | 切换上面两个状态                                                                               | 6        | 手动让程序「坏掉」                                 |
| `GET /slow?seconds=N`                     | 睡眠 N 秒再返回                                                                                | 6        | 探针的超时设置                                     |
| `POST /eat?mb=N`                          | 申请 N MB 内存，并一直占着不释放                                                               | 7        | OOMKilled、requests 和 limits                      |
| `GET /stream`                             | SSE 接口，每 0.5 秒发一个 `tick` 事件，一共 10 个                                              | 8        | 经过 Ingress 时流式输出会不会被缓冲                |
| `GET /gpu`                                | 在 Jetson 上返回 `torch.cuda.is_available()`，以及一次矩阵乘法的耗时                           | 11       | GPU 调度（这个接口单独写成一个小脚本，见第 11 课） |

**要求：**

- 只用 FastAPI 和 uvicorn，配置全部通过环境变量读取。
- Dockerfile 以 `python:3.11-slim` 为基础，镜像尽量小。
- 镜像 tag 用 `kube-toy:v1`、`v2` 这样的形式，**不用 `latest`**。

---

## 4. 仓库结构

```
k8s-learning/
├── CLAUDE.md            # 给 Claude Code 的教学规则（新会话会自动读取）
├── spec.md              # 本文件
├── README.md            # 进度表 + 每课链接（由你维护）
├── app/                 # kube-toy：main.py、requirements.txt、Dockerfile
├── kind/cluster.yaml    # learn 集群的配置
├── lessons/
│   ├── 00-setup/
│   │   └── README.md    # 课堂笔记，模板见下面
│   ├── 01-pod/
│   │   ├── pod.yaml
│   │   └── README.md
│   └── ...
└── chart/kube-toy/      # 第 9 课才出现
```

### 每课的笔记模板（`lessons/NN-xxx/README.md`）

```markdown
# 第 N 课：<概念>

## 目标

## 概念（用我自己的话写）

## 我的预测 → 实际结果

| 操作 | 我预测 | 实际 | 为什么 |

## 命令记录

## 踩坑记录（每个坑都标上类别：K8s / shell·工具 / 程序）

## 自测题和我的回答

## 对应 LexisAI 的哪一行（文件:行号）
```

### Git 的用法

- **每一课提交一次**，提交信息的格式是 `lesson NN: <概念>`，然后推送到 GitHub 上的公开仓库 `k8s-learning`。
- 笔记里「预测」「自测题回答」「概念」这几部分**由你自己写**，Claude 只负责检查，不替你写。

---

## 5. 课程（共 13 课，大约 19 小时）

每节课都按同一个循环进行：

**讲概念 → 你预测会发生什么 → 你动手 → 观察结果 → 解释和预测的差别 → 答自测题 → 提交**

| 课  | 主题                          | 时长 | 学完能看懂 LexisAI 的什么                               |
| --- | ----------------------------- | ---- | ------------------------------------------------------- |
| 0   | 准备工作                      | 1.5h | `deploy/kind/cluster.yaml`、`kind load`                 |
| 1   | Pod                           | 1h   | 为什么 port-forward 一断就要重开                        |
| 2   | Deployment                    | 1.5h | `replicas`、`selector`、`strategy`                      |
| 3   | Service                       | 1.5h | Service 的写法，以及 CI 里那次 503                      |
| 4   | ConfigMap 和 Secret           | 1.5h | `envFrom`、`existingSecret`，以及 secret 末尾换行那个坑 |
| 5   | 存储（PVC）                   | 1.5h | PVC、`subPath`、`Recreate`、`resource-policy: keep`     |
| 6   | 探针                          | 1.5h | backend 的 readiness 和 liveness 为什么那样设           |
| 7   | 资源与 QoS                    | 1.5h | requests 和 limits、那次 OOM、lease 没有被杀的原因      |
| 8   | Ingress                       | 1.5h | `ingress.yaml`、Traefik、SSE、测速脚本那个坑            |
| 9   | Helm                          | 2h   | 整个 chart，以及 Traefik 的配置为什么被悄悄忽略         |
| 10  | 镜像仓库和多架构镜像          | 1.5h | LX-1 第 ⑥ 步要做的事                                    |
| 11  | Jetson：GPU 节点和跨机器调用  | 2h   | `nvidia-device-plugin.yml`，以及 LX-2 的整体架构        |
| 12  | 期末：逐行讲 LexisAI 的 chart | 1h   | 全部                                                    |

### 第 0 课：准备工作

- **目标：** 把 `kube-toy` 的第一版（只有 `GET /`）写出来，在本地跑通，打成镜像，再放进 kind 集群。
- **步骤：**
  1. 删掉 lexisai 集群，新建 `learn` 集群（`kind/cluster.yaml`，预先映射 80/443 端口，第 8 课要用）。
  2. 写 `main.py`，先用 `uvicorn` 在本机跑起来，用 curl 测试。
  3. 写 Dockerfile，`docker build -t kube-toy:v1`，用 `docker run` 测试。
  4. `kind load docker-image kube-toy:v1 --name learn`。
  5. 建好 GitHub 仓库，完成第一次提交。
- **预测题：** 第 4 步之前，集群能直接使用你 Mac 上的镜像吗？为什么？
- **要分清楚的：** 「在 Docker 里跑容器」和「在 K8s 里跑容器」，到底差在哪里？

### 第 1 课：Pod

- **概念：** Pod 是最小的运行单位；它是一次性的；一个 Pod 可以装多个容器（这次只用一个）。
- **练习：**
  1. 手写 `pod.yaml`，然后 `kubectl apply`。
  2. 练习 `get -o wide`、`describe`、`logs`、`exec` 这几个命令。
  3. 用 `port-forward` 访问它。
  4. 删掉这个 Pod。
- **预测题：** 删掉 Pod 以后，它会自己回来吗？port-forward 会怎么样？
- **自测题：** `describe` 最下面的 Events 一般能告诉你什么？`imagePullPolicy` 用默认值时，能不能拉到用 `kind load` 放进去的镜像？

### 第 2 课：Deployment

- **概念：** Deployment 管着 ReplicaSet，ReplicaSet 管着 Pod；label 和 selector；滚动更新和回滚。
- **练习：**
  1. 用 `replicas: 3` 起 3 个副本，手动删掉一个，用 `-w` 观察它被补回来。
  2. 改一下 `APP_VERSION`，打成 `v2`，看着新旧 Pod 一个个替换。
  3. 执行 `rollout undo` 回滚。
  4. 对比 `strategy: Recreate` 和默认的 RollingUpdate。
- **预测题：** 把 Pod 的 label 改得和 selector 对不上，会发生什么？
- **自测题：** 镜像的 tag 不变、只是重新 build 了一次，Pod 会更新吗？（对应 LexisAI 里需要 `rollout restart` 的那个坑。）

### 第 3 课：Service

- **概念：**
  - ClusterIP、DNS 名称（`<svc>.<ns>.svc.cluster.local`）。
  - **Endpoints**：Service 背后实际有哪些 Pod 的 IP。
  - `port` 和 `targetPort` 的区别。
- **练习：**
  1. 起一个临时的 busybox 或 curl Pod，在里面多次 curl 你的 Service，观察每次返回的 `pod` 名字变化。
  2. `kubectl get endpointslices`，查看 Service 背后实际有哪些 Pod。
  3. 把副本数缩到 0，再扩回来，看 endpoints 怎么变。
- **预测题：** Pod 刚变成 Ready 的那一瞬间，Service 能马上把请求转给它吗？
  - 这道题对应 LexisAI CI 里那次 503。答案是不能马上，中间有一段延迟。
- **自测题：** 为什么不直接用 Pod 的 IP 去访问它？

### 第 4 课：ConfigMap 和 Secret

- **概念：**
  - 通过 `env`、`envFrom` 读取，或者以文件形式挂载。
  - **环境变量只在容器启动时读取一次。**
  - Secret 只是 base64 编码，并不是加密。
- **练习：**
  1. 用 ConfigMap 传 `GREETING`，用 Secret 传 `API_TOKEN`，然后通过 `/config` 查看。
  2. 修改 ConfigMap，观察程序有没有读到新值；重启 Pod 以后再看一次。
  3. **换行符实验：** 分别用 `echo "abc" | kubectl create secret ... --from-file=` 和 `printf %s abc` 两种方式创建 Secret，再用 `/config` 显示的最后一个字符看出它们的区别。
- **预测题：** 以文件形式挂载的 ConfigMap，被修改以后，文件内容会变吗？环境变量呢？
- **自测题：** 为什么 LexisAI 的 Secret 不放进 chart 里？

### 第 5 课：存储（PVC）

- **概念：** `emptyDir` 和 PVC 的区别；StorageClass（kind 默认的是 `standard`）；ReadWriteOnce；`subPath`。
- **练习：**
  1. 先用 `emptyDir` 写几条 note，删掉 Pod，看数据还在不在。
  2. 换成 PVC，再做一遍。
  3. 一个 PVC 同时给 2 个副本使用，再用 RollingUpdate 更新一次，观察会出什么问题。
- **预测题：** 删掉 Deployment 以后，PVC 和里面的数据还在吗？
- **自测题：** 为什么 LexisAI 的 backend 要用 `Recreate`？`helm.sh/resource-policy: keep` 防的是什么？

### 第 6 课：探针

- **概念：** readiness、liveness、startup 三种探针；`periodSeconds`、`timeoutSeconds`、`failureThreshold` 这几个参数是怎么配合的。
- **练习：**
  1. 设 `STARTUP_SECONDS=20`，观察 Pod 的 READY 一栏从 `0/1` 变成 `1/1`。
  2. 调用 `/admin/unready`，观察 endpoints 变化（Pod 被摘掉，但不会重启）。
  3. 调用 `/admin/sick`，观察 RESTARTS 加 1。
  4. 把 liveness 的超时设得比 `/slow` 的睡眠时间还短，观察会发生什么。
- **预测题：** readiness 失败的时候，Pod 会被重启吗？
- **自测题：** 为什么 liveness 不应该去检查外部依赖（比如 OpenAI）？为什么 LexisAI 的 liveness 要设成连续失败 3 次、每次间隔 20 秒？

### 第 7 课：资源与 QoS

- **概念：** requests 和 limits 的区别；`OOMKilled` 和退出码 137；三种 QoS 等级（Guaranteed、Burstable、BestEffort）；**CPU 不设 limit 的理由**。
- **练习：**
  1. 设 `limits.memory: 150Mi`，然后调用 `/eat?mb=200`，在 `describe` 里看到 `OOMKilled`。
  2. 把 requests 设成比节点还大，观察 Pod 卡在 `Pending`，并读懂 Events 里的原因。
  3. 去掉 resources，看 QoS 变成 `BestEffort`。
  4. 读容器里的 `/sys/fs/cgroup/memory.peak` 和 `memory.events`。
- **预测题：** `kubectl top` 显示的内存已经顶到 limit 了，进程就一定会被杀吗？
  - 这道题对应 lease 没有被杀的原因：limit 里包含页缓存，内核会先回收缓存。
- **自测题：** 先装 metrics-server，`kubectl top` 才有数据。为什么 kind 默认不装它，而 k3s 自带？

### 第 8 课：Ingress

- **概念：**
  - Ingress（只是一份规则）和 Ingress Controller（真正干活的程序）的区别。
  - `pathType: Prefix` 是按路径段匹配的。
  - hostPort。
  - 为什么选 Traefik（ingress-nginx 已经退役）。
- **练习：**
  1. 用 Helm 安装 Traefik。**这一课只把 Helm 当成安装工具来用，不讲它的原理。**
  2. 把 `kube-toy` 部署两次（v1 和 v2），配一个 Ingress，让 `/v1` 和 `/v2` 分别转给它们。
  3. 通过 Ingress 访问 `/stream`，**用逐行读取的脚本**给每个事件打上时间戳，确认它们是陆续到达的。
- **预测题：** 用 `for line in sys.stdin` 读取管道来打时间戳，结果会怎样？
  - 这道题对应 LexisAI 里那个「全是 4.02 秒」的坑。
- **自测题：** `kubectl get ingress` 的 ADDRESS 一栏为什么是空的？

### 第 9 课：Helm

- **概念：** chart 的结构；`values.yaml` 和环境专用的 values 是怎么合并的（深度合并）；`if`、`with`、`range`、`$`；`toYaml | nindent`；`{{-` 吃掉空白。
- **练习：**
  1. 把第 2–8 课手写的 YAML 改写成 `chart/kube-toy`，必须渲染出和手写版**一模一样**的结果。
  2. 用 `helm template` 和 `helm lint` 检查。
  3. 用 `helm install`、`upgrade`、`rollback` 管理发布，并查看 `helm history`。
  4. **故意写错 values 里的一个键**，观察 Helm 会不会报错，再用 `helm get values` 找出问题。
- **预测题：** values 里写了一个模板根本没用到的键，Helm 会报错吗？
  - 这道题对应 Traefik 的 `service.type` 被悄悄忽略的那个坑。
- **自测题：** `values-kind.yaml` 只写了 `limits.memory`，`requests` 是从哪里来的？

### 第 10 课：镜像仓库和多架构镜像

- **概念：** 镜像仓库（registry）、tag 和 digest 的区别、`imagePullPolicy`；CPU 架构（amd64 和 arm64）；multi-arch manifest（一个 tag 对应多个架构的镜像）。
- **练习：**
  1. 用 `docker buildx` 构建 `linux/amd64` 和 `linux/arm64` 两个架构，推送到 `ghcr.io/<你>/kube-toy`。
  2. 把这个包设成 public（GHCR 新建的包默认是私有的）。
  3. 让集群从 GHCR 拉取镜像，不再用 `kind load`。
  4. 用 `docker manifest inspect` 查看里面有哪些架构。
- **预测题：** 包还是私有的时候，集群去拉它会看到什么错误？
- **自测题：** 为什么 LexisAI 的前端镜像要用空的 `NEXT_PUBLIC_API_BASE` 来 build，才能在所有环境通用？

### 第 11 课：Jetson：GPU 节点和跨机器调用（为 LX-2 做准备）

- **概念：**
  - kubeconfig 里的多个 context，以及怎么切换（**每次操作前都要先确认自己连的是哪个集群**）。
  - device plugin、RuntimeClass、`nvidia.com/gpu` 资源。
  - NodePort。
  - 跨集群调用。
- **练习：**
  1. 把 Jetson 的 kubeconfig 拷到 Mac 上，改好里面的 server 地址，合并进本机的 kubeconfig，用 `kubectl config use-context` 切换。
     - k3s 的证书里默认可能没有 Tailscale 的 IP，到时候会遇到 TLS 报错。可以在 Jetson 的 `/etc/rancher/k3s/config.yaml` 里加上 `tls-san`，或者改用局域网 IP（需要 sudo，由你执行）。
  2. 把 `/gpu` 写成一个只用标准库的小脚本（`http.server` + `torch`），用 ConfigMap 挂载进已经缓存在 Jetson 上的 `pytorch:24.12-py3-igpu` 镜像，这样**不用自己 build 镜像**。
     - Pod 里设置 `runtimeClassName: nvidia`，并申请 `nvidia.com/gpu: 1`。
  3. 开一个 NodePort Service 把它暴露出去。
  4. 从 kind 里的一个 Pod 去 curl `http://<Jetson IP>:<nodePort>/gpu`。
  5. 用 tegrastats 对比加载模型前后的内存，记下差值。LX-2 要测 reranker 的内存时，用的就是这个方法。
- **预测题：** 再起一个同样申请 `nvidia.com/gpu: 1` 的 Pod，会发生什么？
  - 答案是会卡在 `Pending`。GPU 本身就是一种调度约束。
- **自测题：** device plugin 为什么要设 `DEVICE_DISCOVERY_STRATEGY=tegra`？为什么 LX-2 里 Mac 调用 Jetson 用的是 NodePort，而不是 Ingress？

### 第 12 课：期末，逐行讲 LexisAI 的 chart

- **形式：** 你打开 LexisAI 的 `deploy/` 和 `.github/workflows/ci.yml` 里的 `k8s-smoke`，**逐行讲**每一行在做什么、为什么这么写；Claude 只提问，不讲解。
- **过关标准：**
  - 能回答下面这些问题，每个问题都能对应到你某一课的笔记：
    - 为什么 backend 只能有 1 个副本
    - readiness 和 liveness 有什么区别
    - 为什么 kind 上的内存上限要设成 2560Mi
    - 为什么要用 `resource-policy: keep`
    - 为什么前端用相对路径
    - CI 里那次 503 和 secret 换行，分别是怎么回事
  - 过关以后，回到 LexisAI 做 LX-1 的第 ⑥ 步，然后做 LX-2。

---

## 6. 进度和时间安排

- **总共 2 周，大约 19 小时**：第 1 周学第 0–6 课，第 2 周学第 7–12 课。
- 某节课超时了，**宁可拆成两次上，也不要跳过「预测」和「自测题」**。
- 如果第 11 课卡在环境问题上（比如 TLS、网络），超过 1 小时就先记下问题，跳到第 12 课，等做 LX-2 时再回来解决。
