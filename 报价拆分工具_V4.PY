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
        "name": "整箱/整袋模式",
        "pattern": r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*(?:/箱|箱|/袋|袋)',
        "description": "处理如'2880g/箱'的整箱模式，直接提取总重",
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
        if rule_name == "相加模式" or "相加" in rule_name:
            return process_addition_rule(match)
        elif "乘法" in rule_name or "整箱" in rule_name:
            return process_multiplication_rule(match, rule_name)
        else:
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
    """处理乘法模式 - 支持只有2个组的情况（如整箱模式）"""
    groups = match.groups()
    
    if len(groups) >= 2:
        weight_per_unit = float(groups[0])
        unit = groups[1].lower()
        # 兼容只有2个组的情况（如 2880g/箱），数量默认为1
        count = float(groups[2]) if len(groups) > 2 and groups[2] else 1
        
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
        if unit in ['l', '升']:
            weight = weight * 1000
        return weight
    else:
        return 0

def extract_simple_weight(name):
    """提取简单重量模式"""
    simple_patterns = [
        (r'(\d+(?:\.\d+)?)\s*(kg|千克|KG)', 1000, 'kg'),
        (r'(\d+(?:\.\d+)?)(kg|千克|KG)', 1000, 'kg'),
        (r'(\d+(?:\.\d+)?)\s*(g|克|G)', 1, 'g'),
        (r'(\d+(?:\.\d+)?)(g|克|G)', 1, 'g'),
        (r'(\d+(?:\.\d+)?)\s*斤', 500, '斤'),
        (r'(\d+(?:\.\d+)?)斤', 500, '斤'),
        (r'(\d+(?:\.\d+)?)\s*(ml|毫升|ML)', 1, 'ml'),
        (r'(\d+(?:\.\d+)?)(ml|毫升|ML)', 1, 'ml'),
        (r'(\d+(?:\.\d+)?)\s*(L|升)', 1000, 'L'),
        (r'(\d+(?:\.\d+)?)(L|升)', 1000, 'L'),
    ]
    
    for pattern, multiplier, unit in simple_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            try:
                weight = float(match.group(1))
                weight_g = weight * multiplier
                
                count = 1
                count_match = re.search(r'(\d+)\s*(?:包|袋|瓶|盒|箱|件|个|条|只|枚)', name)
                if count_match:
                    count = int(count_match.group(1))
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
        self.rule_window.geometry("800x700")
        self.rule_window.transient(self.parent.window)
        self.rule_window.grab_set()
        
        title_label = tk.Label(self.rule_window, text="重量解析规则管理", 
                               font=("微软雅黑", 14, "bold"))
        title_label.pack(pady=10)
        
        instruction = """在这里管理重量解析规则。每条规则包含一个正则表达式模式，用于从商品名称中提取重量信息。
规则将按照列表顺序依次尝试匹配，直到找到匹配的规则。"""
        instruction_label = tk.Label(self.rule_window, text=instruction, 
                                     justify=tk.LEFT, font=("微软雅黑", 10),
                                     wraplength=750)
        instruction_label.pack(pady=5)
        
        list_frame = tk.Frame(self.rule_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(listbox_frame, text="规则列表", font=("微软雅黑", 11)).pack(anchor=tk.W)
        
        listbox_frame_inner = tk.Frame(listbox_frame)
        listbox_frame_inner.pack(fill=tk.BOTH, expand=True)
        
        self.rules_listbox = tk.Listbox(listbox_frame_inner, font=("微软雅黑", 10))
        self.rules_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        list_scrollbar = tk.Scrollbar(listbox_frame_inner)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rules_listbox.config(yscrollcommand=list_scrollbar.set)
        list_scrollbar.config(command=self.rules_listbox.yview)
        
        self.rules_listbox.bind('<<ListboxSelect>>', self.on_rule_select)
        
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
        
        edit_frame = tk.Frame(list_frame)
        edit_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        tk.Label(edit_frame, text="示例名称 (智能生成):", font=("微软雅黑", 10), fg="blue").pack(anchor=tk.W)
        example_input_frame = tk.Frame(edit_frame)
        example_input_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.example_name_var = tk.StringVar()
        self.example_name_entry = tk.Entry(example_input_frame, textvariable=self.example_name_var, 
                                           font=("微软雅黑", 10))
        self.example_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(example_input_frame, text="生成正则", command=self.generate_regex, 
                  font=("微软雅黑", 9), bg="#e1f5fe").pack(side=tk.LEFT, padx=5)

        self.preview_label = tk.Label(edit_frame, text="", 
                                      justify=tk.LEFT, font=("微软雅黑", 9), 
                                      fg="#2e7d32", bg="#e8f5e9", 
                                      wraplength=350, relief="solid", bd=1, padx=5, pady=5)
        self.preview_label.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(edit_frame, text="规则名称:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.rule_name_var = tk.StringVar()
        self.rule_name_entry = tk.Entry(edit_frame, textvariable=self.rule_name_var, 
                                        font=("微软雅黑", 10))
        self.rule_name_entry.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(edit_frame, text="正则表达式模式:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.pattern_text = tk.Text(edit_frame, height=4, font=("Consolas", 10))
        self.pattern_text.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(edit_frame, text="规则描述:", font=("微软雅黑", 10)).pack(anchor=tk.W)
        self.desc_text = tk.Text(edit_frame, height=3, font=("微软雅黑", 10))
        self.desc_text.pack(fill=tk.X, pady=(0, 10))
        
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_check = tk.Checkbutton(edit_frame, text="启用此规则", 
                                           variable=self.enabled_var,
                                           font=("微软雅黑", 10))
        self.enabled_check.pack(anchor=tk.W, pady=(0, 10))
        
        edit_buttons_frame = tk.Frame(edit_frame)
        edit_buttons_frame.pack(fill=tk.X)
        
        tk.Button(edit_buttons_frame, text="添加新规则", command=self.add_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_buttons_frame, text="更新规则", command=self.update_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(edit_buttons_frame, text="测试规则", command=self.test_rule,
                  font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=2)
        
        bottom_frame = tk.Frame(self.rule_window)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(bottom_frame, text="保存并关闭", command=self.save_and_close,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom_frame, text="重置为默认", command=self.reset_to_default,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        tk.Button(bottom_frame, text="取消", command=self.rule_window.destroy,
                  font=("微软雅黑", 10)).pack(side=tk.RIGHT, padx=5)
        
        self.refresh_rules_list()

    def generate_regex(self):
        """根据示例商品名称智能生成正则表达式并预览结果"""
        input_text = self.example_name_var.get().strip()
        if not input_text:
            messagebox.showwarning("提示", "请输入示例商品名称")
            return
        
        regex_pattern = ""
        rule_name = "自定义规则"
        rule_desc = ""
        
        has_add = '+' in input_text
        has_mul = '*' in input_text or '×' in input_text or 'x' in input_text
        has_paren = '(' in input_text and ')' in input_text
        
        units = ['g', 'kg', '斤', 'ml', 'L', '升', '毫升']
        has_weight = any(u in input_text for u in units)
        
        count_units = ['包', '袋', '瓶', '盒', '箱', '件', '个', '条', '片', '块']
        has_count = any(cu in input_text for cu in count_units)
        
        if has_add and has_weight:
            regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*\+\s*[^\d]*(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)'
            rule_name = "自动生成-相加模式"
            rule_desc = f"处理如'{input_text}'的相加模式"
            
        elif has_mul and has_weight and has_paren:
            regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*\([^)]*\)\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(包|袋|瓶|盒|箱|件)'
            rule_name = "自动生成-带括号乘法"
            rule_desc = f"处理如'{input_text}'的带括号模式"
            
        elif has_mul and has_weight:
            parts = re.split(r'[*×xX]', input_text)
            if len(parts) >= 3:
                regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*\d+\s*[个条块片只]\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(包|袋|瓶|盒|箱|件)'
                rule_name = "自动生成-多重乘法"
            else:
                if has_count:
                    regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*(条|个|包|袋|瓶|盒|箱|件|片|块)'
                    rule_name = "自动生成-简单乘法(带单位)"
                else:
                    regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)\s*[*×xX]\s*(\d+(?:\.\d+)?)(?:\s*包|\s*袋|\s*瓶|\s*盒|\s*箱|\s*件|\s*个|\s*条|$)'
                    rule_name = "自动生成-简单乘法(无单位)"
            rule_desc = f"处理如'{input_text}'的乘法模式"
            
        elif has_weight:
            regex_pattern = r'(\d+(?:\.\d+)?)\s*(g|kg|斤|ml|L|升|毫升)'
            rule_name = "自动生成-简单重量"
            rule_desc = f"处理如'{input_text}'的简单重量模式"
        else:
            messagebox.showwarning("无法识别", "无法从示例名称中识别出重量、乘法或相加模式。\n请确保名称中包含 g/kg/斤 或 */+ 符号。")
            self.preview_label.config(text="❌ 未能识别模式", fg="red")
            return

        self.rule_name_var.set(rule_name)
        self.pattern_text.delete(1.0, tk.END)
        self.pattern_text.insert(1.0, regex_pattern)
        self.desc_text.delete(1.0, tk.END)
        self.desc_text.insert(1.0, rule_desc)
        self.enabled_var.set(True)
        
        try:
            temp_rule = {
                "name": rule_name,
                "pattern": regex_pattern,
                "description": rule_desc,
                "enabled": True
            }
            
            weight_g, raw_weight, raw_unit, count, parse_desc = extract_weight_from_name(input_text, [temp_rule])
            
            if weight_g is not None and weight_g > 0:
                weight_jin = weight_g / 500
                preview_text = f"✅ 测试匹配成功：\n"
                preview_text += f"提取总重: {weight_g}g ({weight_jin:.2f}斤)\n"
                preview_text += f"原始数据: {raw_weight}{raw_unit} × {count}\n"
                preview_text += f"解析说明: {parse_desc}"
                self.preview_label.config(text=preview_text, fg="#2e7d32", bg="#e8f5e9")
            else:
                self.preview_label.config(text="⚠️ 生成的规则未能成功解析该示例，\n请检查或手动修正正则。", fg="orange", bg="#fff3e0")
        except Exception as e:
            self.preview_label.config(text=f"⚠️ 预览出错: {str(e)}", fg="red", bg="#ffebee")
    
    def refresh_rules_list(self):
        self.rules_listbox.delete(0, tk.END)
        for i, rule in enumerate(self.rules):
            status = "✓" if rule.get("enabled", True) else "✗"
            self.rules_listbox.insert(tk.END, f"{status} {rule['name']}")
    
    def on_rule_select(self, event):
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
            self.example_name_var.set("")
            self.preview_label.config(text="")
    
    def add_rule(self):
        name = self.rule_name_var.get().strip()
        pattern = self.pattern_text.get(1.0, tk.END).strip()
        description = self.desc_text.get(1.0, tk.END).strip()
        enabled = self.enabled_var.get()
        
        if not name or not pattern:
            messagebox.showerror("错误", "规则名称和模式不能为空")
            return
        
        try:
            re.compile(pattern)
        except re.error as e:
            messagebox.showerror("错误", f"正则表达式模式无效: {e}")
            return
        
        new_rule = {"name": name, "pattern": pattern, "description": description, "enabled": enabled}
        self.rules.append(new_rule)
        save_rules(self.rules) # 自动保存
        
        self.refresh_rules_list()
        self.rule_name_var.set("")
        self.pattern_text.delete(1.0, tk.END)
        self.desc_text.delete(1.0, tk.END)
        self.example_name_var.set("")
        self.preview_label.config(text="")
        self.enabled_var.set(True)
        messagebox.showinfo("成功", "规则已添加并保存")
    
    def update_rule(self):
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
        
        try:
            re.compile(pattern)
        except re.error as e:
            messagebox.showerror("错误", f"正则表达式模式无效: {e}")
            return
        
        self.rules[self.selected_rule_index] = {"name": name, "pattern": pattern, "description": description, "enabled": enabled}
        save_rules(self.rules) # 自动保存
        self.refresh_rules_list()
        messagebox.showinfo("成功", "规则已更新并保存")
    
    def delete_rule(self):
        if self.selected_rule_index is None:
            messagebox.showerror("错误", "请先选择一个规则")
            return
        
        if messagebox.askyesno("确认", "确定要删除这个规则吗？"):
            self.rules.pop(self.selected_rule_index)
            self.selected_rule_index = None
            save_rules(self.rules) # 自动保存
            self.refresh_rules_list()
            self.rule_name_var.set("")
            self.pattern_text.delete(1.0, tk.END)
            self.desc_text.delete(1.0, tk.END)
            self.example_name_var.set("")
            self.preview_label.config(text="")
            self.enabled_var.set(True)
    
    def move_up(self):
        if self.selected_rule_index is None or self.selected_rule_index == 0: return
        self.rules[self.selected_rule_index], self.rules[self.selected_rule_index-1] = \
            self.rules[self.selected_rule_index-1], self.rules[self.selected_rule_index]
        self.selected_rule_index -= 1
        save_rules(self.rules) # 自动保存
        self.refresh_rules_list()
        self.rules_listbox.select_set(self.selected_rule_index)
    
    def move_down(self):
        if self.selected_rule_index is None or self.selected_rule_index == len(self.rules)-1: return
        self.rules[self.selected_rule_index], self.rules[self.selected_rule_index+1] = \
            self.rules[self.selected_rule_index+1], self.rules[self.selected_rule_index]
        self.selected_rule_index += 1
        save_rules(self.rules) # 自动保存
        self.refresh_rules_list()
        self.rules_listbox.select_set(self.selected_rule_index)
    
    def toggle_rule(self):
        if self.selected_rule_index is None:
            messagebox.showerror("错误", "请先选择一个规则")
            return
        rule = self.rules[self.selected_rule_index]
        rule["enabled"] = not rule.get("enabled", True)
        save_rules(self.rules) # 自动保存
        self.refresh_rules_list()
    
    def test_rule(self):
        pattern = self.pattern_text.get(1.0, tk.END).strip()
        if not pattern:
            messagebox.showerror("错误", "请输入要测试的正则表达式模式")
            return
        
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
                    result_text.insert(tk.END, f"匹配成功!\n\n匹配的文本: {match.group(0)}\n\n捕获组:\n")
                    for i, group in enumerate(match.groups(), 1):
                        result_text.insert(tk.END, f"  组 {i}: {group}\n")
                else:
                    result_text.insert(tk.END, "没有匹配到任何内容")
            except re.error as e:
                result_text.insert(tk.END, f"正则表达式错误: {e}")
        
        tk.Button(test_window, text="测试", command=do_test, font=("微软雅黑", 10)).pack(pady=5)
    
    def reset_to_default(self):
        if messagebox.askyesno("确认", "确定要重置为默认规则吗？当前所有自定义规则将丢失。"):
            self.rules = DEFAULT_RULES.copy()
            self.selected_rule_index = None
            save_rules(self.rules) # 自动保存
            self.refresh_rules_list()
            self.rule_name_var.set("")
            self.pattern_text.delete(1.0, tk.END)
            self.desc_text.delete(1.0, tk.END)
            self.example_name_var.set("")
            self.preview_label.config(text="")
            self.enabled_var.set(True)
    
    def save_and_close(self):
        if save_rules(self.rules):
            self.rule_window.destroy()
        else:
            messagebox.showerror("错误", "保存规则失败")

class ExcelProcessorApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("商品报价拆分工具 - 支持自定义规则")
        self.window.geometry("700x600")
        self.window.resizable(False, False)
        
        try: self.window.iconbitmap('icon.ico')
        except: pass
        
        self.setup_ui()
        self.rule_manager = RuleManager(self)
        
        try:
            import tkinter.dnd as dnd
            self.window.drop_target_register('*')
            self.window.dnd_bind('<<Drop>>', self.on_drop)
        except: pass
    
    def setup_ui(self):
        tk.Label(self.window, text="商品报价拆分工具 - 支持自定义规则", 
                 font=("微软雅黑", 16, "bold")).pack(pady=10)
        
        instruction = """功能：从Excel文件中提取商品总重量信息，计算每斤价格
支持格式：简单重量、乘法、多重乘法、带括号、相加、自定义解析
特殊逻辑：
- 提取示例结果并预览
- 如果「单位」列是「斤」且总重量>1斤，则折算单价；否则直接取价
- 支持自定义规则"""
        
        tk.Label(self.window, text=instruction, justify=tk.LEFT, font=("微软雅黑", 10), wraplength=650).pack(pady=5)
        tk.Frame(self.window, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=10, pady=10)
        
        file_frame = tk.Frame(self.window)
        file_frame.pack(pady=10)
        
        self.file_label = tk.Label(file_frame, text="未选择文件", font=("微软雅黑", 10), width=50, bg="#f0f0f0", relief="solid", anchor="w")
        self.file_label.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(file_frame, text="选择文件", command=self.select_file, font=("微软雅黑", 10), width=10).pack(side=tk.LEFT)
        tk.Button(file_frame, text="管理解析规则", command=self.manage_rules, font=("微软雅黑", 10), width=12).pack(side=tk.LEFT, padx=5)
        
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(self.window, variable=self.progress_var, maximum=100, length=600).pack(pady=10)
        
        self.status_label = tk.Label(self.window, text="等待处理...", font=("微软雅黑", 10))
        self.status_label.pack(pady=5)
        
        self.process_btn = tk.Button(self.window, text="开始处理", command=self.process_file, font=("微软雅黑", 12), width=15, height=2, state=tk.DISABLED)
        self.process_btn.pack(pady=10)
        
        result_frame = tk.LabelFrame(self.window, text="处理结果", font=("微软雅黑", 11))
        result_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.result_text = tk.Text(result_frame, height=12, font=("微软雅黑", 9))
        self.result_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(self.result_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.result_text.yview)
    
    def select_file(self):
        try:
            file_path = filedialog.askopenfilename(title="选择Excel文件", filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")])
            if file_path: self.set_file(file_path)
        except Exception as e: self.show_error(f"选择文件时出错: {str(e)}")
    
    def set_file(self, file_path):
        self.file_path = file_path
        self.file_label.config(text=os.path.basename(file_path))
        self.process_btn.config(state=tk.NORMAL)
        self.status_label.config(text="文件已选择，可以开始处理")
        self.result_text.delete(1.0, tk.END)
    
    def manage_rules(self):
        self.rule_manager.show_rule_manager()
    
    def on_drop(self, event):
        try:
            file_path = event.data
            if file_path.startswith('{') and file_path.endswith('}'): file_path = file_path[1:-1]
            if os.path.isfile(file_path) and (file_path.endswith('.xlsx') or file_path.endswith('.xls')):
                self.set_file(file_path)
            else: messagebox.showerror("错误", "请拖拽有效的Excel文件（.xlsx 或 .xls）")
        except Exception as e: self.show_error(f"拖拽文件时出错: {str(e)}")
    
    def process_file(self):
        if not hasattr(self, 'file_path') or not self.file_path:
            messagebox.showerror("错误", "请先选择文件")
            return
        
        self.process_btn.config(state=tk.DISABLED, text="处理中...")
        self.status_label.config(text="正在处理...")
        self.progress_var.set(0)
        self.result_text.delete(1.0, tk.END)
        
        try: self.window.after(100, self._process_file_worker)
        except Exception as e: self.show_error(f"启动处理时出错: {str(e)}")
    
    def _process_file_worker(self):
        try:
            self.status_label.config(text="正在读取文件...")
            self.window.update()
            
            df = pd.read_excel(self.file_path)
            total_rows = len(df)
            
            price_column = find_price_column(df)
            if price_column is None:
                raise ValueError(f"找不到价格列。可用列名: {df.columns.tolist()}")
            
            custom_rules = load_rules()
            results = []
            success_count = 0
            
            for index, row in df.iterrows():
                product_name = str(row['商品名称']) if '商品名称' in df.columns and pd.notna(row['商品名称']) else ''
                try: price = float(row[price_column]) if pd.notna(row[price_column]) else 0
                except: price = 0
                
                # === 获取「单位」列的值 ===
                unit_from_col = ""
                if '单位' in df.columns and pd.notna(row['单位']):
                    unit_from_col = str(row['单位'])
                # ============================
                
                # 解析名称（获取重量数据用于显示，但在特定逻辑下可能不用于计算价格）
                weight_g, raw_weight, raw_unit, count, parse_desc = extract_weight_from_name(product_name, custom_rules)
                
                price_per_jin = None
                weight_jin = weight_g / 500 if weight_g is not None else 0
                
                # === 核心逻辑：处理「单位」列 ===
                if '斤' in unit_from_col:
                    # 优化：虽然单位是斤，但如果解析出的总重量 > 1斤，说明价格是总价，需要除法
                    if weight_jin is not None and weight_jin > 1:
                        price_per_jin = price / weight_jin
                        parse_desc = f"单位列为斤但总重{weight_jin:.1f}斤，已折算单价"
                    else:
                        # 解析不出重量或重量<=1，默认认为价格就是单价
                        price_per_jin = price
                        parse_desc = "单位列为斤，直接取价"
                    success_count += 1
                else:
                    # 原有计算逻辑（当单位列不是斤，或没有单位列时）
                    if weight_g is not None and weight_g > 0:
                        if weight_jin > 0:
                            if raw_unit and '斤' in raw_unit.lower():
                                price_per_jin = price
                            else:
                                price_per_jin = price / weight_jin
                            success_count += 1
                        else:
                            price_per_jin = None
                    else:
                        weight_jin = None
                        price_per_jin = None
                # ============================================
                
                result_row = {col: row[col] for col in df.columns}
                result_row['提取总重量'] = weight_g
                result_row['提取总重量(斤)'] = round(weight_jin, 3) if weight_jin is not None else None
                result_row['原始单位重量'] = raw_weight
                result_row['原始单位'] = raw_unit
                result_row['包装数量'] = count
                
                if price_per_jin is not None:
                    result_row['每斤价格'] = round(price_per_jin, 2)
                    result_row['每500g价格'] = round(price_per_jin, 2)
                else:
                    result_row['每斤价格'] = None
                    result_row['每500g价格'] = None
                
                result_row['解析说明'] = parse_desc
                
                results.append(result_row)
                
                if (index + 1) % 10 == 0 or (index + 1) == total_rows:
                    progress = ((index + 1) / total_rows) * 100
                    self.progress_var.set(progress)
                    self.status_label.config(text=f"正在处理: {index + 1}/{total_rows} ({progress:.1f}%)")
                    self.window.update()
            
            df_processed = pd.DataFrame(results)
            base_name = os.path.splitext(self.file_path)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{base_name}_处理后_{timestamp}.xlsx"
            
            self.status_label.config(text="正在保存结果...")
            self.window.update()
            df_processed.to_excel(output_file, index=False)
            
            self.progress_var.set(100)
            self.status_label.config(text="处理完成！")
            self.process_btn.config(state=tk.NORMAL, text="开始处理")
            
            result_text = f"✓ 处理完成！\n\n输出文件: {output_file}\n价格列: {price_column}\n使用规则数: {len([r for r in custom_rules if r.get('enabled', True)])}\n\n统计信息:\n总商品数: {total_rows}\n成功提取: {success_count}\n成功率: {success_count/total_rows*100:.1f}%\n"
            
            if success_count > 0:
                price_data = df_processed['每斤价格'].dropna()
                avg_price = round(price_data.mean(), 2)
                min_price = round(price_data.min(), 2)
                max_price = round(price_data.max(), 2)
                result_text += f"\n价格统计:\n平均每斤价格: {avg_price}元\n最低每斤价格: {min_price}元\n最高每斤价格: {max_price}元\n"
            
            result_text += f"\n解析示例:\n"
            sample_rows = df_processed.head(10)
            for _, row in sample_rows.iterrows():
                if '解析说明' in row:
                    weight_jin = row['提取总重量(斤)']
                    price_per_jin = row['每斤价格']
                    result_text += f"- {row['商品名称']}: {row['解析说明']}"
                    if weight_jin and price_per_jin:
                        result_text += f" → {weight_jin:.1f}斤, {price_per_jin:.2f}元/斤\n"
                    else:
                        result_text += "\n"
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, result_text)
            
            self.window.after(1000, lambda: self.ask_open_file(output_file))
            
        except Exception as e:
            self.show_error(f"处理过程中出错: {str(e)}\n\n{traceback.format_exc()}")
            self.process_btn.config(state=tk.NORMAL, text="开始处理")
    
    def ask_open_file(self, output_file):
        if os.path.exists(output_file):
            if messagebox.askyesno("处理完成", f"处理完成！\n\n文件已保存到:\n{output_file}\n\n是否要打开文件？"):
                try:
                    if sys.platform == 'win32': os.startfile(output_file)
                    elif sys.platform == 'darwin': os.system(f'open "{output_file}"')
                    else: os.system(f'xdg-open "{output_file}"')
                except: pass
    
    def show_error(self, error_msg):
        if len(error_msg) > 500: error_msg = error_msg[:500] + "..."
        messagebox.showerror("错误", error_msg)
        self.process_btn.config(state=tk.NORMAL, text="开始处理")
        self.status_label.config(text="处理失败")
    
    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    app = ExcelProcessorApp()
    app.run()