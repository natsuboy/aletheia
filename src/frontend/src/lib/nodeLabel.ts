import type { NodeLabel } from '@/types/graph';

const NODE_LABEL_TEXT: Record<NodeLabel, string> = {
  Project: '项目',
  Package: '包',
  Module: '模块',
  Folder: '目录',
  File: '文件',
  Class: '类',
  Function: '函数',
  Method: '方法',
  Variable: '变量',
  Interface: '接口',
  Enum: '枚举',
  Decorator: '装饰器',
  Import: '导入',
  Type: '类型',
  CodeElement: '代码元素',
  Community: '社区',
  Process: '流程',
};

export function formatNodeLabel(label: NodeLabel): string {
  return NODE_LABEL_TEXT[label] || label;
}

