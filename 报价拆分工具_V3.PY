import pandas as pd
import re
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback
from datetime import datetime
import json

# 规则配置文件路径
RULES_FILE = "weight_rules.json"

# 默认规则
DEFAULT_RULES = [
    {
        "name": "相加模式",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*\+\s*[^\d]*(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)',
        "description": "处理如'150g+调料包230g'的相加模式",
        "enabled": True
    },
    {
        "name": "带括号乘法模式",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*\([^)]*\)\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(包|袋|瓶|盒|箱|件)',
        "description": "处理如'310g(10个)*20包'的模式",
        "enabled": True
    },
    {
        "name": "多重乘法模式",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*\d+\s*[个条块片只]\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(包|袋|瓶|盒|箱|件)',
        "description": "处理如'30g*10个*20包'的多重乘法",
        "enabled": True
    },
    {
        "name": "简单乘法模式1",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(条|个|包|袋|瓶|盒|箱|件|片|块)',
        "description": "处理如'100g*40条'的简单乘法",
        "enabled": True
    },
    {
        "name": "简单乘法模式2",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*(\d+(?:\.\d+)?)(?:\s*包|\s*袋|\s*瓶|\s*盒|\s*箱|\s*件|\s*个|\s*条|$)',
        "description": "处理如'2.5kg*4'的简单乘法",
        "enabled": True
    }
]

def load_rules():
    """加载规则"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_RULES
    else:
        return DEFAULT_RULES

def save_rules(rules):
    """保存规则"""
    try:
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def extract_weight_from_name(name, custom_rules=None):
    """从商品名称中提取重量信息（总重量）"""
    if not isinstance(name, str):
        return None, None, None, 1, ""
    
    name = str(name)
    
    # 加载规则
    rules = custom_rules if custom_rules else load_rules()
    
    # 只启用启用的规则
    enabled_rules = [rule for rule in rules if rule.get("enabled", True)]
    
    for rule in enabled_rules:
        try:
            pattern = rule["pattern"]
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                # 根据规则名称调用相应的处理函数
                result = process_rule_match(rule["name"], match, name)
                if result:
                    return result
        except Exception as e:
            print(f"规则 {rule['name']} 执行错误: {e}")
            continue
    
    # 如果没有匹配任何规则，尝试简单重量模式
    return extract_simple_weight(name)

def process_rule_match(rule_name, match, original_name):
    """根据规则名称处理匹配结果"""
    try:
        if rule_name == "相加模式":
            return process_addition_rule(match)
        elif "乘法" in rule_name:
            return process_multiplication_rule(match, rule_name)
        else:
            # 默认处理，可以扩展更多规则类型
            return process_general_rule(match, rule_name)
    except Exception as e:
        print(f"处理规则 {rule_name} 时出错: {e}")
        return None

def process_addition_rule(match):
    """处理相加模式"""
    weight1 = float(match.group(1))
    unit1 = match.group(2).lower()
    weight2 = float(match.group(3))
    unit2 = match.group(4).lower()
    
    # 转换为克
    weight1_g = convert_to_grams(weight1, unit1)
    weight2_g = convert_to_grams(weight2, unit2)
    
    if weight1_g == 0 and weight2_g == 0:
        return None
    
    total_weight_g = weight1_g + weight2_g
    return total_weight_g, weight1, unit1, 1, f"相加模式: {weight1}{unit1}+{weight2}{unit2}={total_weight_g/1000:.2f}kg"

def process_multiplication_rule(match, rule_name):
    """处理乘法模式"""
    groups = match.groups()
    
    if len(groups) >= 3:
        weight_per_unit = float(groups[0])
        unit = groups[1].lower()
        count = float(groups[2]) if groups[2] else 1
        
        # 转换为克
        weight_per_unit_g = convert_to_grams(weight_per_unit, unit)
        
        if weight_per_unit_g == 0:
            return None
        
        total_weight_g = weight_per_unit_g * count
        
        # 获取计数单位
        count_unit = groups[3] if len(groups) > 3 and groups[3] else ""
        
        return total_weight_g, weight_per_unit, unit, int(count), f"{rule_name}: {weight_per_unit}{unit}×{count}{count_unit}={total_weight_g/1000:.2f}kg"
    
    return None

def process_general_rule(match, rule_name):
    """处理通用规则"""
    # 这里可以添加更多特定规则的逻辑
    # 目前使用默认的乘法处理
    return process_multiplication_rule(match, rule_name)

def convert_to_grams(weight, unit):
    """将重量转换为克"""
    unit = unit.lower()
    if unit in ['kg', '千克']:
        return weight * 1000
    elif unit in ['g', '克']:
        return weight
    elif unit == '斤':
        return weight * 500
    elif unit in ['ml', '毫升', 'l', '升']:
        # 假设液体密度接近水
        if unit in ['l', '升']:
            weight = weight * 1000  # 转换为毫升
        return weight
    else:
        return 0

def extract_simple_weight(name):
    """提取简单重量模式"""
    simple_patterns = [
        # 千克模式
        (r'(\d+(?:\.\d+)?)\s*(kg|千克|KG)', 1000, 'kg'),
        (r'(\d+(?:\.\d+)?)(kg|千克|KG)', 1000, 'kg'),
        
        # 克模式
        (r'(\d+(?:\.\d+)?)\s*(g|克|G)', 1, 'g'),
        (r'(\d+(?:\.\d+)?)(g|克|G)', 1, 'g'),
        
        # 斤模式
        (r'(\d+(?:\.\d+)?)\s*斤', 500, '斤'),
        (r'(\d+(?:\.\d+)?)斤', 500, '斤'),
        
        # 毫升模式
        (r'(\d+(?:\.\d+)?)\s*(ml|毫升|ML)', 1, 'ml'),
        (r'(\d+(?:\.\d+)?)(ml|毫升|ML)', 1, 'ml'),
        
        # 升模式
        (r'(\d+(?:\.\d+)?)\s*(L|升)', 1000, 'L'),
        (r'(\d+(?:\.\d+)?)(L|升)', 1000, 'L'),
    ]
    
    for pattern, multiplier, unit in simple_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            try:
                weight = float(match.group(1))
                weight_g = weight * multiplier
                
                # 尝试提取包装数量
                count = 1
                count_match = re.search(r'(\d+)\s*(?:包|袋|瓶|盒|箱|件|个|条|只|枚)', name)
                if count_match:
                    count = int(count_match.group(1))
                    # 如果已经提取了重量，且是单个重量，则乘以数量
                    if re.search(r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L)\s*[*×xX]', name) is None:
                        weight_g = weight_g * count
                
                return weight_g, weight, unit, count, f"简单模式: {weight}{unit}" + (f"×{count}" if count>1 else "")
            except:
                continue
    
    return None, None, None, 1, "无法解析重量"

def find_price_column(df):
    """查找价格列"""
    possible_names = [
        '12.22-12.28确认价格',
        '确认价格',
        '价格',
        '单价',
        '报价',
        'price',
        'Price',
        'PRICE'
    ]
    
    for name in possible_names:
        if name in df.columns:
            return name
    
    # 如果没有找到标准名称，查找包含"价格"或"price"的列
    for col in df.columns:
        if isinstance(col, str) and ('价格' in col or 'price' in col.lower()):
            return col
    
    return None

class RuleManager:
    """规则管理器"""
    def __init__(self, parent):
        self.parent = parent
        self.rules = load_rules()
        self.selected_rule_index = None
        
    def show_rule_manager(self):
        """显示规则管理器窗口"""
        self.rule_window = tk.Toplevel(self.parent.window)
        self.rule_window.title("重量解析规则管理")
        self.rule_window.geometry("800x600")
        self.rule_window.transient(self.parent.window)
        self.rule_window.grab_set()
        
        # 标题
        title_label = tk.Label(self.rule_window, text="重量解析规则管理", 
                               font=("微软雅黑", 14, "bold"))
        title_label.pack(pady=10)
        
        # 说明
        instruction = """在这里管理重量解析规则。每条规则包含一个正则表达式模式，用于从商品名称中提取重量信息。
规则将按照列表顺序依次尝试匹配，直到找到匹配的规则。"""
        instruction_label = tk.Label(self.rule_window, text=instruction, 
                                     justify=tk.LEFT, font=("微软雅黑", 10),
                                     wraplength=750)
        instruction_label.pack(pady=5)
        
        # 规则列表框架
        list_frame = tk.Frame(self.rule_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 规则列表
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(listbox_frame, text="规则列表", font=("微软雅黑", 11)).pack(anchor=tk.W)
        
        # 创建列表框和滚动条
        listbox_frame_inner = tk.Frame(listbox_frame)
        listbox_frame_inner.pack(fill=tk.BOTH, expand=True)
        
        self.rules_listbox = tk.Listbox(listbox_frame_inner, font=("微软雅黑", 10))
        self.rules_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        list_scrollbar = tk.Scrollbar(listbox_frame_inner)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rules_listbox.config(yscrollcommand=list_scrollbar.set)
        list_scrollbar.config(command=self.rules_listbox.yview)
        
        # 绑定选择事件
        self.rules_listbox.bind('<<ListboxSelect>>', self.on_rule_select)
        
        # 按钮框架
        button_frame = tk.Frame(listbox_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(button_frame, text="上移", command=self.move_up, 
                  font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="下移", command=self.move_down,
                  font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="启用/禁用", command=self.toggle_rule,
                  font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="删除", command=self.delete_rule,
                  font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=2)
        
        # 规则编辑框架
        edit_frame = tk.Frame(list_frame)
        edit_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # 规则名称
        tk.Label(edit_frame, text="规则名称:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.rule_name_var = tk.StringVar()
        self.rule_name_entry = tk.Entry(edit_frame, textvariable=self.rule_name_var, 
                                        font=("微软雅黑", 10))
        self.rule_name_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 正则表达式模式
        tk.Label(edit_frame, text="正则表达式模式:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.pattern_text = tk.Text(edit_frame, height=4, font=("Consolas", 10))
        self.pattern_text.pack(fill=tk.X, pady=(0, 10))
        
        # 规则描述
        tk.Label(edit_frame, text="规则描述:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.desc_text = tk.Text(edit_frame, height=3, font=("微软雅黑", 10))
        self.desc_text.pack(fill=tk.X, pady=(0, 10))
        
        # 启用状态
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_check = tk.Checkbutton(edit_frame, text="启用此规则", 
                                           variable=self.enabled_var,
                                           font=("微软雅黑", 10))
        self.enabled_check.pack(anchor=tk.W, pady=(0, 10))
        
        # 按钮框架
        edit_buttons_frame = tk.Frame(edit_frame)
        edit_buttons_frame.pack(fill=tk.X)
        
        tk.Button(edit_buttons_frame, text="添加新规则", command=self.add_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_buttons_frame, text="更新规则", command=self.update_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_buttons_frame, text="测试规则", command=self.test_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        
        # 底部按钮
        bottom_frame = tk.Frame(self.rule_window)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(bottom_frame, text="保存并关闭", command=self.save_and_close,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom_frame, text="重置为默认", command=self.reset_to_default,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom_frame, text="取消", command=self.rule_window.destroy,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        
        # 加载规则到列表
        self.refresh_rules_list()
    
    def refresh_rules_list(self):
        """刷新规则列表"""
        self.rules_listbox.delete(0, tk.END)
        for i, rule in enumerate(self.rules):
            status = "✓" if rule.get("enabled", True) else "✗"
            self.rules_listbox.insert(tk.END, f"{status} {rule['name']}")
    
    def on_rule_select(self, event):
        """当选择规则时"""
        selection = self.rules_listbox.curselection()
        if selection:
            self.selected_rule_index = selection[0]
            rule = self.rules[self.selected_rule_index]
            
            self.rule_name_var.set(rule.get("name", ""))
            self.pattern_text.delete(1.0, tk.END)
            self.pattern_text.insert(1.0, rule.get("pattern", ""))
            self.desc_text.delete(1.0, tk.END)
            self.desc_text.insert(1.0, rule.get("description", ""))
            self.enabled_var.set(rule.get("enabled", True))
    
    def add_rule(self):
        """添加新规则"""
        name = self.rule_name_var.get().strip()
        pattern = self.pattern_text.get(1.0, tk.END).strip()
        description = self.desc_text.get(1.0, tk.END).strip()
        enabled = self.enabled_var.get()
        
        if not name or not pattern:
            messagebox.showerror("错误", "规则名称和模式不能为空")
            return
        
        # 检查模式是否有效
        try:
            re.compile(pattern)
        except re.error as e:
            messagebox.showerror("错误", f"正则表达式模式无效: {e}")
            return
        
        new_rule = {
            "name": name,
            "pattern": pattern,
            "description": description,
            "enabled": enabled
        }
        
        self.rules.append(new_rule)
        self.refresh_rules_list()
        
        # 清空表单
        self.rule_name_var.set("")
        self.pattern_text.delete(1.0, tk.END)
        self.desc_text.delete(1.0, tk.END)
        self.enabled_var.set(True)
        
        messagebox.showinfo("成功", "规则已添加")
    
    def update_rule(self):
        """更新规则"""
        if self.selected_rule_index is None:
            messagebox.showerror("错误", "请先选择一个规则")
            return
        
        name = self.rule_name_var.get().strip()
        pattern = self.pattern_text.get(1.0, tk.END).strip()
        description = self.desc_text.get(1.0, tk.END).strip()
        enabled = self.enabled_var.get()
        
        if not name or not pattern:
            messagebox.showerror("错误", "规则名称和模式不能为空")
            return
        
        # 检查模式是否有效
        try:
            re.compile(pattern)
        except re.error as e:
            messagebox.showerror("错误", f"正则表达式模式无效: {e}")
            return
        
        self.rules[self.selected_rule_index] = {
            "name": name,
            "pattern": pattern,
            "description": description,
            "enabled": enabled
        }
        
        self.refresh_rules_list()
        messagebox.showinfo("成功", "规则已更新")
    
    def delete_rule(self):
        """删除规则"""
        if self.selected_rule_index is None:
            messagebox.showerror("错误", "请先选择一个规则")
            return
        
        if messagebox.askyesno("确认", "确定要删除这个规则吗？"):
            self.rules.pop(self.selected_rule_index)
            self.selected_rule_index = None
            self.refresh_rules_list()
            
            # 清空表单
            self.rule_name_var.set("")
            self.pattern_text.delete(1.0, tk.END)
            self.desc_text.delete(1.0, tk.END)
            self.enabled_var.set(True)
    
    def move_up(self):
        """上移规则"""
        if self.selected_rule_index is None or self.selected_rule_index == 0:
            return
        
        # 交换位置
        self.rules[self.selected_rule_index], self.rules[self.selected_rule_index-1] = \
            self.rules[self.selected_rule_index-1], self.rules[self.selected_rule_index]
        
        self.selected_rule_index -= 1
        self.refresh_rules_list()
        self.rules_listbox.select_set(self.selected_rule_index)
    
    def move_down(self):
        """下移规则"""
        if self.selected_rule_index is None or self.selected_rule_index == len(self.rules)-1:
            return
        
        # 交换位置
        self.rules[self.selected_rule_index], self.rules[self.selected_rule_index+1] = \
            self.rules[self.selected_rule_index+1], self.rules[self.selected_rule_index]
        
        self.selected_rule_index += 1
        self.refresh_rules_list()
        self.rules_listbox.select_set(self.selected_rule_index)
    
    def toggle_rule(self):
        """切换规则启用状态"""
        if self.selected_rule_index is None:
            messagebox.showerror("错误", "请先选择一个规则")
            return
        
        rule = self.rules[self.selected_rule_index]
        rule["enabled"] = not rule.get("enabled", True)
        self.refresh_rules_list()
    
    def test_rule(self):
        """测试规则"""
        pattern = self.pattern_text.get(1.0, tk.END).strip()
        if not pattern:
            messagebox.showerror("错误", "请输入要测试的正则表达式模式")
            return
        
        # 测试窗口
        test_window = tk.Toplevel(self.rule_window)
        test_window.title("测试规则")
        test_window.geometry("500x300")
        test_window.transient(self.rule_window)
        
        tk.Label(test_window, text="输入商品名称进行测试:", 
                 font=("微软雅黑", 10)).pack(anchor=tk.W, padx=10, pady=5)
        
        test_entry = tk.Entry(test_window, font=("微软雅黑", 10), width=50)
        test_entry.pack(fill=tk.X, padx=10, pady=5)
        
        result_text = tk.Text(test_window, height=10, font=("Consolas", 9))
        result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def do_test():
            product_name = test_entry.get().strip()
            if not product_name:
                messagebox.showerror("错误", "请输入商品名称")
                return
            
            result_text.delete(1.0, tk.END)
            
            try:
                match = re.search(pattern, product_name, re.IGNORECASE)
                if match:
                    result_text.insert(tk.END, f"匹配成功!\n\n")
                    result_text.insert(tk.END, f"匹配的文本: {match.group(0)}\n\n")
                    result_text.insert(tk.END, f"捕获组:\n")
                    for i, group in enumerate(match.groups(), 1):
                        result_text.insert(tk.END, f"  组 {i}: {group}\n")
                else:
                    result_text.insert(tk.END, "没有匹配到任何内容")
            except re.error as e:
                result_text.insert(tk.END, f"正则表达式错误: {e}")
        
        tk.Button(test_window, text="测试", command=do_test,
                  font=("微软雅黑", 10)).pack(pady=5)
    
    def reset_to_default(self):
        """重置为默认规则"""
        if messagebox.askyesno("确认", "确定要重置为默认规则吗？当前所有自定义规则将丢失。"):
            self.rules = DEFAULT_RULES.copy()
            self.refresh_rules_list()
            self.selected_rule_index = None
            
            # 清空表单
            self.rule_name_var.set("")
            self.pattern_text.delete(1.0, tk.END)
            self.desc_text.delete(1.0, tk.END)
            self.enabled_var.set(True)
    
    def save_and_close(self):
        """保存并关闭"""
        if save_rules(self.rules):
            messagebox.showinfo("成功", "规则已保存")
            self.rule_window.destroy()
        else:
            messagebox.showerror("错误", "保存规则失败")

class ExcelProcessorApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("商品报价拆分工具 - 支持自定义规则")
        self.window.geometry("700x600")
        
        # 防止窗口大小被调整
        self.window.resizable(False, False)
        
        # 设置窗口图标（如果有）
        try:
            self.window.iconbitmap('icon.ico')
        except:
            pass
        
        self.setup_ui()
        
        # 初始化规则管理器
        self.rule_manager = RuleManager(self)
        
        # 支持拖拽
        try:
            import tkinter.dnd as dnd
            self.window.drop_target_register('*')
            self.window.dnd_bind('<<Drop>>', self.on_drop)
        except:
            pass
    
    def setup_ui(self):
        """设置用户界面"""
        # 标题
        title_label = tk.Label(self.window, text="商品报价拆分工具 - 支持自定义规则", 
                               font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=10)
        
        # 说明
        instruction = """功能：从Excel文件中提取商品总重量信息，计算每斤价格
支持格式：
- 简单重量：冻鱿鱿鱼筒2kg
- 乘法模式：高技日本豆腐100g*40条
- 多重乘法：大笑绿茶芋卷30g*10个*20包
- 带括号：冻品先生深海鳕鳕鱼排310g(10个)*20包
- 相加模式：紫燕夫妻肺片微辣150g+调料包230g
- 支持自定义解析规则"""
        
        instruction_label = tk.Label(self.window, text=instruction, 
                                     justify=tk.LEFT, font=("微软雅黑", 10),
                                     wraplength=650)
        instruction_label.pack(pady=5)
        
        # 分隔线
        separator = tk.Frame(self.window, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill=tk.X, padx=10, pady=10)
        
        # 文件选择区域
        file_frame = tk.Frame(self.window)
        file_frame.pack(pady=10)
        
        self.file_label = tk.Label(file_frame, text="未选择文件", 
                                   font=("微软雅黑", 10), width=50, 
                                   bg="#f0f0f0", relief="solid", anchor="w")
        self.file_label.pack(side=tk.LEFT, padx=(0, 10))
        
        btn_select = tk.Button(file_frame, text="选择文件", 
                              command=self.select_file, 
                              font=("微软雅黑", 10), width=10)
        btn_select.pack(side=tk.LEFT)
        
        # 规则管理按钮
        btn_rules = tk.Button(file_frame, text="管理解析规则", 
                             command=self.manage_rules, 
                             font=("微软雅黑", 10), width=12)
        btn_rules.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.window, variable=self.progress_var, 
                                           maximum=100, length=600)
        self.progress_bar.pack(pady=10)
        
        # 状态文本
        self.status_label = tk.Label(self.window, text="等待处理...", 
                                     font=("微软雅黑", 10))
        self.status_label.pack(pady=5)
        
        # 处理按钮
        self.process_btn = tk.Button(self.window, text="开始处理", 
                                     command=self.process_file, 
                                     font=("微软雅黑", 12),
                                     width=15, height=2,
                                     state=tk.DISABLED)
        self.process_btn.pack(pady=10)
        
        # 结果区域
        result_frame = tk.LabelFrame(self.window, text="处理结果", 
                                     font=("微软雅黑", 11))
        result_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # 创建文本框用于显示结果
        self.result_text = tk.Text(result_frame, height=12, font=("微软雅黑", 9))
        self.result_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(self.result_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.result_text.yview)
    
    def select_file(self):
        """选择文件"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择Excel文件",
                filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
            )
            
            if file_path:
                self.set_file(file_path)
        except Exception as e:
            self.show_error(f"选择文件时出错: {str(e)}")
    
    def set_file(self, file_path):
        """设置文件路径"""
        self.file_path = file_path
        self.file_label.config(text=os.path.basename(file_path))
        self.process_btn.config(state=tk.NORMAL)
        self.status_label.config(text="文件已选择，可以开始处理")
        self.result_text.delete(1.0, tk.END)
    
    def manage_rules(self):
        """管理解析规则"""
        self.rule_manager.show_rule_manager()
    
    def on_drop(self, event):
        """拖拽文件到窗口"""
        try:
            # 获取拖拽的文件路径
            file_path = event.data
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            
            if os.path.isfile(file_path) and (file_path.endswith('.xlsx') or file_path.endswith('.xls')):
                self.set_file(file_path)
            else:
                messagebox.showerror("错误", "请拖拽有效的Excel文件（.xlsx 或 .xls）")
        except Exception as e:
            self.show_error(f"拖拽文件时出错: {str(e)}")
    
    def process_file(self):
        """处理文件"""
        if not hasattr(self, 'file_path') or not self.file_path:
            messagebox.showerror("错误", "请先选择文件")
            return
        
        # 禁用处理按钮
        self.process_btn.config(state=tk.DISABLED, text="处理中...")
        self.status_label.config(text="正在处理...")
        self.progress_var.set(0)
        self.result_text.delete(1.0, tk.END)
        
        try:
            # 在同一个线程中处理，但使用after来更新UI
            self.window.after(100, self._process_file_worker)
        except Exception as e:
            self.show_error(f"启动处理时出错: {str(e)}")
    
    def _process_file_worker(self):
        """处理文件的工作函数"""
        try:
            # 读取数据
            self.status_label.config(text="正在读取文件...")
            self.window.update()
            
            df = pd.read_excel(self.file_path)
            total_rows = len(df)
            
            # 查找价格列
            price_column = find_price_column(df)
            if price_column is None:
                raise ValueError(f"找不到价格列。可用列名: {df.columns.tolist()}")
            
            # 加载自定义规则
            custom_rules = load_rules()
            
            results = []
            success_count = 0
            
            # 处理每一行
            for index, row in df.iterrows():
                # 获取商品名称
                if '商品名称' in df.columns:
                    product_name = str(row['商品名称']) if pd.notna(row['商品名称']) else ''
                else:
                    product_name = ''
                
                # 获取价格
                try:
                    price = float(row[price_column]) if pd.notna(row[price_column]) else 0
                except:
                    price = 0
                
                # 提取重量（使用自定义规则）
                weight_g, raw_weight, raw_unit, count, parse_desc = extract_weight_from_name(product_name, custom_rules)
                
                # 计算每斤价格
                if weight_g is not None and weight_g > 0:
                    weight_jin = weight_g / 500
                    if weight_jin > 0:
                        price_per_jin = price / weight_jin
                        success_count += 1
                    else:
                        price_per_jin = None
                else:
                    weight_jin = None
                    price_per_jin = None
                
                # 创建结果行
                result_row = {}
                
                # 保留原始所有列
                for col in df.columns:
                    result_row[col] = row[col]
                
                # 添加新列
                result_row['提取总重量(g)'] = weight_g
                result_row['提取总重量(斤)'] = round(weight_jin, 3) if weight_jin else None
                result_row['原始单位重量'] = raw_weight
                result_row['原始单位'] = raw_unit
                result_row['包装数量'] = count
                result_row['每斤价格'] = round(price_per_jin, 2) if price_per_jin else None
                result_row['每500g价格'] = round(price_per_jin, 2) if price_per_jin else None
                result_row['解析说明'] = parse_desc
                
                results.append(result_row)
                
                # 更新进度
                if (index + 1) % 10 == 0 or (index + 1) == total_rows:
                    progress = ((index + 1) / total_rows) * 100
                    self.progress_var.set(progress)
                    self.status_label.config(text=f"正在处理: {index + 1}/{total_rows} ({progress:.1f}%)")
                    self.window.update()
            
            # 转换为DataFrame
            df_processed = pd.DataFrame(results)
            
            # 生成输出文件名
            base_name = os.path.splitext(self.file_path)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{base_name}_处理后_{timestamp}.xlsx"
            
            # 保存结果
            self.status_label.config(text="正在保存结果...")
            self.window.update()
            
            df_processed.to_excel(output_file, index=False)
            
            # 更新UI
            self.progress_var.set(100)
            self.status_label.config(text="处理完成！")
            self.process_btn.config(state=tk.NORMAL, text="开始处理")
            
            # 显示结果
            result_text = f"✓ 处理完成！\n\n"
            result_text += f"输出文件: {output_file}\n"
            result_text += f"价格列: {price_column}\n"
            result_text += f"使用的规则数: {len([r for r in custom_rules if r.get('enabled', True)])}\n\n"
            result_text += f"统计信息:\n"
            result_text += f"总商品数: {total_rows}\n"
            result_text += f"成功提取: {success_count}\n"
            result_text += f"成功率: {success_count/total_rows*100:.1f}%\n"
            
            if success_count > 0:
                price_data = df_processed['每斤价格'].dropna()
                avg_price = round(price_data.mean(), 2)
                min_price = round(price_data.min(), 2)
                max_price = round(price_data.max(), 2)
                
                result_text += f"\n价格统计:\n"
                result_text += f"平均每斤价格: {avg_price}元\n"
                result_text += f"最低每斤价格: {min_price}元\n"
                result_text += f"最高每斤价格: {max_price}元\n"
            
            # 显示解析示例
            result_text += f"\n解析示例:\n"
            sample_rows = df_processed.head(10)
            for _, row in sample_rows.iterrows():
                if '解析说明' in row and row['解析说明'] != "无法解析重量":
                    weight_jin = row['提取总重量(斤)']
                    price_per_jin = row['每斤价格']
                    result_text += f"- {row['商品名称']}: {row['解析说明']}"
                    if weight_jin and price_per_jin:
                        result_text += f" → {weight_jin:.1f}斤, {price_per_jin:.2f}元/斤\n"
                    else:
                        result_text += "\n"
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, result_text)
            
            # 询问是否打开文件
            self.window.after(1000, lambda: self.ask_open_file(output_file))
            
        except Exception as e:
            self.show_error(f"处理过程中出错: {str(e)}\n\n{traceback.format_exc()}")
            self.process_btn.config(state=tk.NORMAL, text="开始处理")
    
    def ask_open_file(self, output_file):
        """询问是否打开文件"""
        if os.path.exists(output_file):
            open_file = messagebox.askyesno("处理完成", 
                                           f"处理完成！\n\n文件已保存到:\n{output_file}\n\n是否要打开文件？")
            if open_file:
                try:
                    if sys.platform == 'win32':
                        os.startfile(output_file)
                    elif sys.platform == 'darwin':  # macOS
                        os.system(f'open "{output_file}"')
                    else:  # Linux
                        os.system(f'xdg-open "{output_file}"')
                except:
                    pass
    
    def show_error(self, error_msg):
        """显示错误信息"""
        # 截断过长的错误信息
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        
        messagebox.showerror("错误", error_msg)
        self.process_btn.config(state=tk.NORMAL, text="开始处理")
        self.status_label.config(text="处理失败")
    
    def run(self):
        """运行应用"""
        self.window.mainloop()

def test_weight_extraction():
    """测试重量提取函数"""
    test_cases = [
        # 格式: (商品名称, 期望总重量(g), 期望解析说明)
        ("冻品先生深海鳕鳕鱼排310g(10个)*20包", 6200, "310g×20包=6.20kg"),
        ("大笑绿茶芋卷30g*10个*20包", 600, "30g×20包=0.60kg"),
        ("大笑吉祥南瓜饼25g*12个*16包", 400, "25g×16包=0.40kg"),
        ("高技日本豆腐100g*40条", 4000, "100g×40条=4.00kg"),
        ("王守义十三香45g*10盒", 450, "45g×10盒=0.45kg"),
        ("安井包心鱼豆腐2.5kg*4", 10000, "2.5kg×4=10.00kg"),
        ("冻品先生黑椒肉柳1kg*10/箱", 10000, "1kg×10=10.00kg"),
        ("安井香酥肉卷2.5kg*4", 10000, "2.5kg×4=10.00kg"),
        ("安井仿蟹柳2.5kg*4", 10000, "2.5kg×4=10.00kg"),
        ("紫燕夫妻肺片微辣150g+调料包230g", 380, "150g+230g=0.38kg"),
        ("千般就黑椒T骨猪扒1kg*10包", 10000, "1kg×10包=10.00kg"),
        ("安井鱼籽包2.5kg/包*4包/箱", 10000, "2.5kg×4包=10.00kg"),
        ("冻鱿鱿鱼筒2kg", 2000, "2kg"),
        ("龙口粉丝500g", 500, "500g"),
    ]
    
    print("测试重量提取函数：")
    print("=" * 80)
    
    for name, expected_g, expected_desc in test_cases:
        weight_g, _, _, _, parse_desc = extract_weight_from_name(name)
        weight_kg = weight_g / 1000 if weight_g else 0
        weight_jin = weight_g / 500 if weight_g else 0
        
        status = "✓" if weight_g == expected_g else "✗✗"
        
        print(f"{status} {name}")
        print(f"  解析: {parse_desc}")
        print(f"  总重量: {weight_kg:.2f}kg = {weight_jin:.1f}斤")
        print(f"  期望重量: {expected_g/1000:.2f}kg = {expected_g/500:.1f}斤")
        if weight_g != expected_g:
            print(f"  ❌❌ 错误: 重量不匹配!")
        print()
    
    print("测试完成!")

def main():
    """主函数"""
    # 如果要测试重量提取，取消下面这行的注释
    # test_weight_extraction()
    
    app = ExcelProcessorApp()
    app.run()

if __name__ == "__main__":
    main()