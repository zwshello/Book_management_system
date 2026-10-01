# 阶段 13：按最新需求跳过

Istio 属于当前项目暂不完成的选做内容。当前版本不使用 Kubernetes，因此也不实现 Istio；它仅是“未来可扩展的服务网格方案”。

已核对 README、AGENTS.md、`docs/` 与 `deploy/istio/`：没有文档声称当前系统已实现 Istio，`deploy/istio/` 仅有简短说明、没有 YAML。阶段 1 需求追踪表已标记阶段 13 跳过；API 文档明确当前内部接口依靠后端鉴权与 Compose 网络隔离。

本阶段未安装 Istio，未生成 VirtualService、DestinationRule，未配置 Sidecar 或 Istio Gateway，未修改业务代码或 Compose。未进入阶段 14。
