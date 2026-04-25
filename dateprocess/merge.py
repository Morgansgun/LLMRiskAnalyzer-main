def merge_markdown(files, output_file):
    with open(output_file, "w", encoding="utf-8") as outfile:
        for i, file in enumerate(files):
            # 打开每个 markdown 文件
            with open(file, "r", encoding="utf-8") as infile:
                content = infile.read()
                # 你可以在文件之间加上分隔符（例如文件名、日期、注释等）
                if i > 0:
                    outfile.write("\n\n" + "="*50 + "\n\n")  # 文件之间的分隔符，可以自定义
                outfile.write(content)
            print(f"已合并: {file}")
    print(f"合并完成，保存为: {output_file}")


# 示例
files = [
    "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/File1.md",
    "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/File2.md",
    "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/File3.md"
]

merge_markdown(files, "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/File.md")
