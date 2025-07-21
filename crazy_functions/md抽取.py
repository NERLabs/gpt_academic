from toolbox import update_ui, promote_file_to_downloadzone
from toolbox import CatchException, report_exception, write_history_to_file
from shared_utils.fastapi_server import validate_path_safety
from crazy_functions.crazy_utils import input_clipping
import json

def 解析MD实体识别核心(file_manifest, project_folder, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt):
    import os, copy
    from crazy_functions.crazy_utils import request_gpt_model_multi_threads_with_very_awesome_ui_and_high_efficiency
    from crazy_functions.crazy_utils import request_gpt_model_in_new_thread_with_ui_alive

    summary_batch_isolation = True
    inputs_array = []
    inputs_show_user_array = []
    history_array = []
    sys_prompt_array = []
    report_part_1 = []

    # 最大处理文件数
    MAX_FILES = 1000
    if len(file_manifest) > MAX_FILES:
        chatbot.append(("警告", f"文件数量超过{MAX_FILES}个，将处理前{MAX_FILES}个文件"))
        yield from update_ui(chatbot=chatbot, history=history)
        file_manifest = file_manifest[:MAX_FILES]

    ############################## <第一步：构建实体分类体系> ##################################
    entity_categories = {
        "品种类": [
            "作物主类", "品质性状", "抗病性", "抗逆性", "生育期",
            "适应性", "用途", "感官品质", "株型"
        ],
        "农事类": [
            "养殖管理", "土壤耕作", "植保作业", "收获处理", "设施维护",
            "资源循环", "农机工作", "农业培训与服务", "灾害应对", "产后加工"
        ],
        "农时类": [
            "节气农时", "物候阶段", "操作窗口", "气候周期", "市场周期",
            "灾害防御期", "生态调控期"
        ],
        "农情类": [
            "生长监测", "土壤条件", "气象条件", "病虫害情况", "杂草与田间杂况"
        ],
        "农艺类": [
            "栽培模式与结构", "育苗与移栽技术", "植株调控措施",
            "精准施肥与灌溉", "田间感知与智能决策"
        ],
        "茬口类": [
            "轮作模式", "连作管理", "间作设计", "套作", "休耕养地",
            "茬口衔接", "接茬风险评估", "复种强度", "土地利用效率", "茬口规划主动性"
        ],
        "未标注实体": ["未分类实体"]
    }
    
    # 构建示例输出结构
    example_output = {main_cat: {sub_cat: [] for sub_cat in sub_cats} 
                     for main_cat, sub_cats in entity_categories.items()}
    
    ############################## <第二步：逐个文件分析> ##################################
    for index, fp in enumerate(file_manifest):
        try:
            if not os.path.exists(fp) or not os.path.isfile(fp):
                continue
                
            with open(fp, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            rel_path = os.path.relpath(fp, project_folder)
            
            # 新的提示词设计
            prompt = f"""请分析以下Markdown文档，按指定格式标注实体：
            
            **文件路径**: {rel_path}
            **文档内容**:
            {md_content[:3000]}... [内容截断]
            
            **实体分类体系**:
            {json.dumps(entity_categories, ensure_ascii=False, indent=2)}
            
            **要求**:
            1. 严格按以下JSON格式输出结果: 
            {json.dumps(example_output, ensure_ascii=False, indent=2)}
            2. 实体必须归类到最具体的子类别
            3. 每个实体只归入一个类别
            4. 未识别实体放入"未标注实体→未分类实体"列表
            5. 最终输出结果必须为md文件中的JSON格式，请勿输出其他内容。
            """
            
            inputs_array.append(prompt)
            inputs_show_user_array.append(f"实体标注 [{index+1}/{len(file_manifest)}]: {rel_path}")
            history_array.append([])
            sys_prompt_array.append("您是农业领域专家，擅长实体分类标注")
            
        except Exception as e:
            chatbot.append([f"处理失败: {os.path.basename(fp)}", str(e)])
            yield from update_ui(chatbot=chatbot, history=history)
            continue

    # 批量处理分析请求
    gpt_response_collection = yield from request_gpt_model_multi_threads_with_very_awesome_ui_and_high_efficiency(
        inputs_array = inputs_array,
        inputs_show_user_array = inputs_show_user_array,
        history_array = history_array,
        sys_prompt_array = sys_prompt_array,
        llm_kwargs = llm_kwargs,
        chatbot = chatbot,
        show_user_at_complete = True
    )

    ############################## <第二步：汇总分析结果> ##################################
    combined_results = ["# Markdown实体分析汇总报告\n"]

    # 添加各文件分析结果
    for fp, analysis in zip(file_manifest, gpt_response_collection[1::2]):
        rel_path = os.path.relpath(fp, project_folder)
        combined_results.append(f"## 文件：{rel_path}\n")
        combined_results.append(analysis + "\n")

    # 跳过汇总统计步骤
    # 直接进入最终报告生成
    final_report = "\n".join(combined_results)
    res = write_history_to_file(combined_results)
    promote_file_to_downloadzone(res, chatbot=chatbot)

    chatbot.append(("分析完成", "实体识别结果已保存（未进行全局汇总）"))
    yield from update_ui(chatbot=chatbot, history=[final_report])

@CatchException
def 解析MD实体识别(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    history = []  # 清空历史
    import glob, os

    # 输入验证
    if not txt.strip():
        report_exception(chatbot, history, a="输入为空", b="请输入文件夹路径")
        yield from update_ui(chatbot=chatbot, history=history)
        return

    project_folder = txt.strip()
    validate_path_safety(project_folder, chatbot.get_user())

    # 收集JSON文件
    file_manifest = glob.glob(f'{project_folder}/**/*.txt', recursive=True)

    if not file_manifest:
        report_exception(chatbot, history, a="无md文件", b=f"目录中未找到md文件: {project_folder}")
        yield from update_ui(chatbot=chatbot, history=history)
        return

    # 开始处理
    yield from 解析MD实体识别核心(
        file_manifest=file_manifest,
        project_folder=project_folder,
        llm_kwargs=llm_kwargs,
        plugin_kwargs=plugin_kwargs,
        chatbot=chatbot,
        history=history,
        system_prompt=system_prompt
    )