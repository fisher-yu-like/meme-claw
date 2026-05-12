from duckduckgo_search import DDGS
import json
results = DDGS().text("python programming", max_results=5)
print(results)
 
# 以 JSON 格式打印结果，indent=2 表示缩进 2 个空格
print(json.dumps(results, indent=2))