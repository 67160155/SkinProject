# main.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import os
import random

# --- ส่วนที่ 1: Import ไฟล์ที่แยกออกมา ---
from skin_analysis import SkinAnalyzer
from product_db import SHOP_INVENTORY, get_product_list_text
from ai_expert import SkinExpertAI
from face_utils import FaceDetector 

app = FastAPI()

# ตรวจสอบและสร้างโฟลเดอร์ static/images ถ้ายังไม่มี
if not os.path.exists("static/images"):
    os.makedirs("static/images")

# Mount โฟลเดอร์ static เพื่อให้เข้าถึงรูปภาพผ่าน /static/images/...
app.mount("/static", StaticFiles(directory="static"), name="static")

# ตั้งค่า API Key และเรียกใช้ Class
GEMINI_API_KEY = 
analyzer = SkinAnalyzer()
ai_bot = SkinExpertAI(GEMINI_API_KEY)
detector = FaceDetector()

# --- ฟังก์ชันกรองสินค้าจากฐานข้อมูล (ส่งข้อมูลครบทุกฟิลด์) ---
def get_recommended_products(oiliness, redness, skin_type):
    recommended = []
    # กำหนด Tag ค้นหาเบื้องต้น
    skin_tag = "oily" if oiliness > 50 else "dry" if oiliness < 20 else "normal"
    if "แพ้ง่าย" in skin_type:
        skin_tag = "sensitive"

    for p in SHOP_INVENTORY:
        if skin_tag in p['tags'] or "all_skin_types" in p['tags']:
            # ส่งข้อมูลให้ครบตามที่ index.html ต้องการแสดงผล
            recommended.append({
                "id": p['id'],
                "brand": p.get('brand', 'Premium Brand'),
                "name": p['name'],
                "price": p['price'],
                "image_url": p['image_url'], # Path จะเป็น /static/images/xxx.webp
                "usage": p.get('usage', 'เช้า-เย็น'),
                "ingredients": p.get('ingredients', 'N/A'),
                "benefits": p.get('benefits', 'N/A'),
                "is_external": p.get('is_external', False),
                "affiliate_link": p.get('affiliate_link', '#')
            })
    
    # สุ่มเลือกมา 3-5 ชิ้นเพื่อให้หน้าจอไม่ซ้ำซาก
    return random.sample(recommended, min(len(recommended), 4))

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/analyze")
async def analyze_endpoint(
    file: UploadFile = File(...), 
    skin_type: str = Form("ไม่ระบุ"), 
    allergies: str = Form("ไม่มี")
):
    try:
        raw_image_data = await file.read()
        
        # 1. ตรวจจับและ Crop ใบหน้า
        cropped_image_bytes = detector.process_and_crop(raw_image_data)
        
        if not cropped_image_bytes:
            return JSONResponse(content={"error": "ไม่สามารถตรวจพบใบหน้าในรูปภาพได้"}, status_code=400)

        # 2. วิเคราะห์ค่าความมันและรอยแดง
        metrics = analyzer.process(cropped_image_bytes)
        
        if not metrics:
            return JSONResponse(content={"error": "วิเคราะห์ผิวไม่สำเร็จ"}, status_code=400)

        # 3. ให้ AI ให้คำแนะนำ (ดึงข้อมูลสรรพคุณ/ส่วนประกอบจากฐานข้อมูล)
        ai_response = ai_bot.consult(metrics, skin_type, allergies)

        # 4. กรองสินค้าจากฐานข้อมูลมาโชว์ที่ Curated for You
        products = get_recommended_products(metrics['oiliness'], metrics['redness'], skin_type)

        # จัดระเบียบข้อมูลส่งกลับ
        return {
            "analysis": metrics,
            "routine": {
                "morning": ["ล้างหน้าให้สะอาด", "ทาผลิตภัณฑ์บำรุง", "ทากันแดดทุกเช้า"],
                "evening": ["เช็ดทำความสะอาด", "ล้างหน้า", "ทาครีมบำรุงก่อนนอน"],
                "ingredients": ai_response.get("recommended_ingredients", ["Ceramide", "Hyaluronic Acid"]),
                "advice": ai_response.get("analysis", "เน้นการบำรุงผิวตามคำแนะนำข้างต้นครับ")
            },
            "products": products
        }
    except Exception as e:
        print(f"Server Error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
