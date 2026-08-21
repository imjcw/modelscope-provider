# services/providers — AI 供应商适配层

## 职责

实现各 AI 供应商的 API 适配,统一接口供上层路由调用。

## 文件说明

| 文件 | 供应商 | 说明 |
|------|--------|------|
| base.py | 基类 | 定义供应商适配器的统一接口 |
| sensetime.py | 商汤科技 | 商汤大模型 API 适配 |
| modelscope.py | ModelScope | 魔搭社区模型 API 适配 |
| per_model.py | 按模型路由 | 每个模型独立配置供应商 |

## 关键约定

- 所有供应商适配器继承 base.py 中的基类
- 适配器负责:认证、请求格式转换、响应解析、错误处理
- 新增供应商:在 providers/ 下新建文件,实现基类接口

## 常见陷阱

- 商汤 GLM-5.2 等模型只有单账号,无兜底,429 会直接返回
- 不同供应商的鉴权方式不同(Bearer Token / API Key 等)
- 响应格式差异需在适配层归一化

## 相关测试

tests/services/providers/ — 覆盖各供应商适配器
