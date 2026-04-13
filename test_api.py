import urllib.request
import json
import time
import sys

def test_api():
    print("1. 正在向 AetherCrawler 提交分析任务 (币种: bitcoin) ...")
    req = urllib.request.Request(
        "http://localhost:8000/analyze-crypto",
        data=json.dumps({"coin": "bitcoin"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            task_id = res["id"]
            celery_task_id = res["celery_task_id"]
            print(f"✅ 任务提交成功！\nTask ID: {task_id}\nCelery Task ID: {celery_task_id}\nStatus: {res['status']}\n")
    except Exception as e:
        print(f"❌ 提交任务失败，请检查服务是否启动: {e}")
        sys.exit(1)

    print(f"2. 开始轮询任务状态 (Task ID: {task_id}) ...")
    max_retries = 30
    for i in range(max_retries):
        try:
            with urllib.request.urlopen(f"http://localhost:8000/tasks/{task_id}") as response:
                res = json.loads(response.read().decode())
                status = res["status"]
                print(f"   [{i+1}/{max_retries}] 当前状态: {status}")
                
                if status in ["SUCCESS", "FAILURE"]:
                    print("\n🎉 分析完成！最终报告如下：")
                    print(json.dumps(res, indent=2, ensure_ascii=False))
                    break
        except Exception as e:
            print(f"❌ 获取任务状态失败: {e}")
            break
            
        time.sleep(5)
    else:
        print("⏳ 轮询超时，任务仍在执行中...")

if __name__ == "__main__":
    test_api()
