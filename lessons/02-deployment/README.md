# 第 2 课：Deployment

## 目标

用 Deployment 让 K8s 一直保持 3 个 `kube-toy` Pod。弄懂 label 和 selector 是怎么"点名"的，看着滚动更新从 v1 换到 v2，用 `rollout undo` 回滚，再和 `strategy: Recreate` 做对比。

## 笔记（用我自己的话写）

## 我的预测 → 实际结果

| 操作                                     | 我预测                                                          | 实际                                                          | 为什么                                                              |
| ---------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------- |
| 3 个 Pod 里删掉 1 个                     | 会重启一个新的 pod，确保数量是 3                                | 补了一个**新的** ✅（名字不同，`RESTARTS 0`），1 秒内 Running | Deployment 一直盯着数量，少了就新建一个，不是重启旧的               |
| 把一个 Pod 的贴纸改成 `app=other`        | 这个 pod 不会被删掉，只有 label 变了；会再开一个新的，总共 4 个 | 4 个 ✅，新开了 `rd8cn`                                       | Deployment 按贴纸点名，只数到 2 个就补 1 个；改了贴纸的那个没人管了 |
| 滚动更新 v1 → v2：一次全换还是一个一个换 | 一个一个换                                                      | 一个一个换 ✅                                                 | RollingUpdate：新的先 Running，旧的才 Terminating                   |
| 滚动更新时最多几个 Pod                   | 还是 3 个，因为 replicas 是 3                                   | **4 个** ❌                                                   | 新的先上岗、旧的再离开，交接时会多出 1 个                           |
| 回滚后 Pod 名字                          | 回到之前 pod 的名字                                             | 中间那串回到 `79885f9f86` ✅，最后 5 个字母是新的             | 重新用了原来那条 ReplicaSet，但 Pod 是新做的                        |
| 回滚后 `version`                         | `v1`                                                            | `dev` ❌                                                      | v1 那版 Pod 模具里没写 `env`，回滚把整个模具都退回去了              |
| Recreate 时最多几个 Pod                  | 3 个                                                            | 3 个 ✅                                                       | 旧的全部关完，新的才开始                                            |
| Recreate 时会不会一个 Running 都没有     | 会                                                              | 会 ✅                                                         | 旧的全部 `Completed` 之后、新的 `Running` 之前，没人接客            |

## 命令记录

```bash
kubectl config current-context                          # kind-learn

# 1. Deployment with 3 replicas, delete one
kubectl apply -f lessons/02-deployment/deployment.yaml
kubectl get pods
kubectl get pods -w                                     # terminal 1, keep watching
kubectl delete pod <pod-name>                           # terminal 2

# 2. labels and selector
kubectl get pods --show-labels
kubectl label pod <pod-name> app=other --overwrite
kubectl get pods -l app=kube-toy                        # what the Deployment "counts"
kubectl delete pod <the-relabeled-pod>                  # clean up the orphan

# 3. rolling update to v2 (image: v2 + env APP_VERSION=v2)
docker build -t kube-toy:v2 app
kind load docker-image kube-toy:v2 --name learn
docker exec learn-control-plane crictl images | grep kube-toy
kubectl apply -f lessons/02-deployment/deployment.yaml
kubectl get rs
kubectl describe deployment kube-toy                    # Events: ScalingReplicaSet
kubectl port-forward deploy/kube-toy 8000:8000
curl localhost:8000/                                    # version: v2

# 4. roll back
kubectl rollout undo deployment/kube-toy
kubectl get rs
kubectl get pods --show-labels
curl localhost:8000/                                    # version: dev

# 5. strategy: Recreate (file still says v2)
kubectl apply -f lessons/02-deployment/deployment.yaml
kubectl describe deployment kube-toy                    # from 0 to 3 in one go
```

## 踩坑记录（每个坑都标上类别：K8s / shell·工具 / 程序）

| 现象                                                             | 原因                                                                                       | 类别     |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | -------- |
| `no matches for kind "Deployment" in version "app/v1"`           | 第一行少了个 `s`，应该是 `apps/v1`；后面那句 `ensure CRDs are installed first` 和这次无关  | K8s 概念 |
| `unknown field "spec.template.metadata.lebals"`                  | `labels` 拼错了；报错里的路径就是 YAML 的缩进层级，顺着找就行                              | K8s 概念 |
| `rollout undo` 报 Warning：`last-applied-configuration` 不会更新 | undo 只改了集群，没改文件；文件还写着 v2，下次 apply 又会变回 v2。正经做法是改文件再 apply | K8s 概念 |
| 以为改贴纸后，那个 Pod 会跟着 Deployment 一起被删                | 改了贴纸就不归 Deployment 管了，要手动删                                                   | K8s 概念 |
| `port-forward deploy/kube-toy` 换版本后断了                      | 它其实只接了其中一个 Pod，那个 Pod 被换掉，管子就断了                                      | K8s 概念 |

## 自测题和我的回答

### 1. 镜像的 tag 不变（比如还是 `kube-toy:v2`），只是改了代码、重新 build 并 kind load 了一次，然后再 `kubectl apply` 同一个 deployment.yaml，Pod 会更新吗？为什么？

答：不会，因为pod中包含的是一个container，更新镜像不会影响pod的存活。

Claude判断答案以及解释：**结论对，原因不对。**

- ✅ 不会更新。
- ❌ 原因不是"Pod 里只有一个容器"。真正的原因是：**Deployment 只看订单有没有变**。`deployment.yaml` 一个字都没改，还是 `image: kube-toy:v2`，K8s 一对比"和现在一样"，就什么都不做。镜像里面的代码变没变，它根本不知道。
- 这一课你亲眼见过：第 5 步改了 `strategy`，但 Pod 模具没变，K8s 就直接用了原来那条 `d966f9bb9`，没有开新的生产线。
- 那该怎么让它更新？用 `kubectl rollout restart deployment/kube-toy`，它会强制按滚动更新把 Pod 全部重做一遍。更好的做法是**每次 build 都换一个新 tag**（v3、v4…），这样订单自然就变了。这就是 spec 要求不用 `latest` 的原因之一。

### 2. RollingUpdate 和 Recreate 换版本时有什么区别？什么情况下只能用 Recreate？

答：一个是一个一个添加，一个是全部关掉，再一次性添加所有。在版本之间有冲突的时候适合使用recreate。

Claude判断答案以及解释：**基本正确。**

- ✅ 区别说对了：RollingUpdate 是新的先起来一个、旧的再关一个；Recreate 是旧的全部关掉，新的再一次全开，中间会有一段没人接客。
- "版本之间有冲突"可以说得更具体：**新旧两个 Pod 不能同时跑**的时候，就只能用 Recreate。最典型的例子是两个 Pod 会同时写**同一个文件**，比如 LexisAI backend 的 SQLite 数据库，同时写可能把数据库写坏。

## 对应 LexisAI 的哪一行（文件:行号）

LexisAI 仓库：`~/Documents/definition_finder/deploy/helm/lexisai/`

- `templates/backend.yaml:25`：`replicas: 1`。SQLite 只允许一个写入者，所以 backend 只能有 1 份。
- `templates/backend.yaml:26-27`：`strategy: type: Recreate`。原因就是自测题 2：RollingUpdate 会让新旧两个 Pod 同时写同一个 SQLite 文件。
- `templates/frontend.yaml:8-10`：frontend **故意不用** Recreate。它没有共享的磁盘，新旧同时跑没问题，所以用默认的 RollingUpdate，换版本时不停服务。
- `README.md:29-30`：用文字解释了 backend 为什么用 Recreate，宁可停几秒，也不让两个 Pod 同时写一个 SQLite。
- `README.md:21`：`After rebuilding an image with the same tag: kind load ... then kubectl rollout restart`，就是自测题 1 那个坑：tag 不变时 apply 不会更新，只能用 `rollout restart`。
