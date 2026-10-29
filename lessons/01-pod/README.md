# 第 1 课：Pod

## 目标

手写 `pod.yaml`，让 K8s 把 `kube-toy:v1` 跑成一个 Pod。学会用 `get -o wide`、`describe`、`logs`、`exec` 查看它，用 `port-forward` 访问它，最后删掉它，看看会发生什么。

## 概念（用我自己的话写）

- 这节课讲了pod是如何创建的，同时说了如何在pod里面拉取image并在pod里把容器跑起来。
- 同时在describe说明下认识到了在启动一个pod会有四个event: Scheduled, Pulled, Created, Stared
- 也说明了pod和version在port-forward这个通道之后会是什么
- 此外，整个oid被删除之后，整个port-forwar通道也会断掉，因为这个通道连接的是pod，pod没有了，自然也是断链了

## 我的预测 → 实际结果

| 操作                                             | 我预测                                                      | 实际                                                             | 为什么                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Pod 跑起来后，`docker ps` 能看到 kube-toy 容器吗 | 会，因为 pod 里面装的就是容器（后来改成：容器在 node 里面） | 看不到；`docker exec learn-control-plane crictl ps` 里才有 `app` | 容器在节点**里面**，`docker ps` 只能看到 Mac 这一层的容器                     |
| `describe` 的 Events 记录了什么                  | 只能看到一个容器被启动了                                    | 4 件：Scheduled → Pulled → Created → Started                     | 启动前还要先选节点、准备镜像、创建容器                                        |
| Pod 里执行 `hostname`                            | 节点的名字（`learn-control-plane`）                         | `kube-toy` ❌                                                    | 每个 Pod 有自己的 hostname，就是 Pod 名                                       |
| port-forward 后 curl 的 `pod`                    | `kube-toy`                                                  | `kube-toy` ✅                                                    | 同上                                                                          |
| port-forward 后 curl 的 `version`                | `v1`，写在 pod.yaml 里                                      | `dev` ❌                                                         | `kube-toy:v1` 的 `v1` 只是镜像标签；YAML 里没传 `APP_VERSION`，程序用了默认值 |
| 删掉 Pod 后，它会自己回来吗                      | 应该会吧（不确定）                                          | 不会 ❌，`No resources found`                                    | 订单只写了"要一个 Pod"，没人负责补                                            |
| 删掉 Pod 后，port-forward 会怎么样               | 应该会吧（不确定）                                          | 断了 ❌，`lost connection to pod`                                | 管子接在那一个 Pod 上，Pod 没了管子就断了                                     |

## 命令记录

```bash
kubectl config current-context                 # kind-learn
kubectl apply -f lessons/01-pod/pod.yaml       # hand the "order" to K8s
kubectl get pods
docker ps                                      # no kube-toy here
docker exec learn-control-plane crictl ps      # it's inside the node

kubectl get pods -o wide                       # IP + which node
kubectl describe pod kube-toy                  # look at Events at the bottom
kubectl logs kube-toy
kubectl exec kube-toy -- hostname              # kube-toy

kubectl port-forward pod/kube-toy 8000:8000    # terminal 1, stays open
curl localhost:8000/                           # terminal 2

kubectl delete pod kube-toy
curl localhost:8000/                           # port-forward breaks here
kubectl get pods                               # No resources found
```

## 踩坑记录（每个坑都标上类别：K8s / shell·工具 / 程序）

| 现象                                        | 原因                                                                              | 类别       |
| ------------------------------------------- | --------------------------------------------------------------------------------- | ---------- |
| `apply` 报 `unknown field "spec.container"` | 少写了一个 `s`，应该是 `containers`；K8s 对 Pod 的字段检查很严格，写错直接拒收    | K8s 概念   |
| curl 返回 `version: dev`，以为会是 `v1`     | 镜像标签 `kube-toy:v1` 和环境变量 `APP_VERSION` 是两回事，YAML 里没有设置环境变量 | K8s 概念   |
| 删掉 Pod 后 port-forward 看起来"没变化"     | port-forward 要等有请求进来才去找 Pod，curl 一次才报错退出                        | shell·工具 |

## 自测题和我的回答

### 1. describe 最下面的 Events 一般能告诉你什么？Pod 起不来的时候，为什么要先看它？

答：最下面的event可以告诉我们目前运行到了什么状态。如果pod起不来，看event可以知道目前的pod是卡在了什么环节，然后可以拆开检查。Scheduled → Pulled → Created → Started

Claude判断答案以及解释：**正确。** Events 就是 Pod 的"物流记录"：最后一条停在哪一步，问题通常就出在下一步。比如停在 `Scheduled`、没有 `Pulled`，就去查镜像。

### 2. imagePullPolicy 的意思是"什么时候去网上下载镜像"。它的默认值是"本地已经有，就不下载"。用这个默认值，能不能用上 kind load 送进去的镜像？请用你今天在 Events 里看到的那一行来说明。

答：应该可以吧，在pulled里面会把镜像准保好，如果本地有的话，就不下载。如果这一步没发完成，就没办法到下一步Created。

Claude判断答案以及解释：**结论对，证据还差一点。**

- ✅ 能用上，而且你说对了：`Pulled` 这一步没完成，就到不了 `Created`。
- 不用说"应该"，Events 里已经写明了：`Container image "kube-toy:v1" already present on machine`。意思是镜像已经在节点上了，所以没去网上下载。这行就是证据。
- 补充一点：这个默认值只在标签**不是** `latest` 的时候才成立。用 `latest` 的话，K8s 每次都会去网上下载，而网上没有你的 `kube-toy`，就会失败。这就是 spec 要求"不用 `latest`"的原因。

## 对应 LexisAI 的哪一行（文件:行号）

LexisAI 仓库里**没有用到 `port-forward`**（搜过整个仓库），它用的是 Ingress（第 8 课）。

spec 里说的"port-forward 一断就要重开"，指的是 LX-1 调试时遇到的现象：port-forward 接的是**某一个具体的 Pod**，Pod 一重建（哪怕名字一样），旧的管子就断了，必须重新执行 `kubectl port-forward`。
