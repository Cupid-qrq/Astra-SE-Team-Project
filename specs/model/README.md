# P0-A4 离线接入准备

发起人于2026-10-24确认：账号和API Key暂未准备，本次仅完成schema、配置和离线测试。当前实现没有网络调用路径，不读取密钥。

`input.schema.json`只允许公开题目/样例、本人代码、语言、脱敏诊断、粗粒度判定和附加问题。`output.schema.json`限定错误类别、定位线索、检查方向、学习建议四段。脚本额外检查输入24KiB、样例每份4KiB、输出2000码点/8KiB；拒绝额外字段、错误类型和重复JSON键。

```powershell
python -m pip install -r tools/requirements-model.txt
python tools/model_probe.py
python -m unittest discover -s tools/tests -p test_model_probe.py -v
```

输出只含输入摘要与离线标记，不输出源码；`actual_cost_cny=null`表示没有真实计费记录，不将未知费用记0。示例代码为项目自编，无真实学生信息。schema校验不能证明字段来源可信、授权有效或正文安全；完整提示安全、配额/双预算、事务预占和真实质量验证仍由P2完成。

## 官方资料核对（2026-10-24）

- [模型和价格](https://api-docs.deepseek.com/quick_start/pricing/)当日列出`deepseek-flash`，对应展示版本DeepSeek-V4.1-Flash-1017；该别名不是不可变版本。英文页面美元计价，峰时未命中输入0.30美元/百万token、输出1.20美元/百万token；谷时分别0.15/0.60。此处仅为资料快照，不作为人民币预算结算配置。
- [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)要求`response_format=json_object`及包含json要求的提示，仍需本地校验空内容、截断和schema；不能仅以供应商JSON模式认定有效。
- [使用条款](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)页面更新日为2026-03-27，涉及输入/输出使用及产品改进用途；专门条款可能优先。隐私政策页面本次读取超时，账号地区、实际适用条款、API数据留存和训练退出机制尚未核实，不能声称已满足数据条款门槛。

启用前由账号持有人确认实际区域、人民币价格/计费币种及转换依据、数据条款和预算。配置保留每日20元/项目500元的规划上限，模型、token上限、价格和核验引用为空且enabled=false。后续需另行实现经审查的真实ModelPort与一次自编样例连通，不通过修改该离线模板的开关启用收费服务。
