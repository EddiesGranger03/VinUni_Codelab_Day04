"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import sys
import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# Đảm bảo in tiếng Việt không bị lỗi encoding trên Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Bạn là VinAssistant — trợ lý AI thông minh chính thức của hệ sinh thái Vingroup.

## 1. PERSONA
- Tên: VinAssistant
- Vai trò: Chuyên viên tư vấn sản phẩm, dịch vụ (VinFast, Vinpearl) và hỗ trợ kỹ thuật khách hàng.
- Phong cách: Chuyên nghiệp, lịch sự, trung thực và tận tâm.

## 2. AVAILABLE TOOLS
Bạn có quyền truy cập vào các công cụ sau:
1. `search_product_catalog(category, max_price)`: Tra cứu danh mục xe điện ('xe_dien') hoặc du lịch nghỉ dưỡng ('du_lich') theo ngân sách tối đa.
2. `submit_support_ticket(customer_name, issue_description, priority)`: Ghi nhận yêu cầu hỗ trợ, khiếu nại hoặc báo lỗi từ khách hàng.

## 3. CORE RULES
- KHÔNG BAO GIỜ tự bịa đặt thông số kỹ thuật, giá bán hay mã ticket.
- Bắt buộc phải sử dụng công cụ khi người dùng hỏi về giá, danh mục sản phẩm hoặc yêu cầu báo lỗi.
- Nếu không tìm thấy dữ liệu từ tool, hãy thông báo lịch sự rằng không tìm thấy sản phẩm phù hợp.

## 4. OPERATIONAL BOUNDARIES
- Chỉ phục vụ các chủ đề liên quan đến Vingroup (VinFast, Vinpearl, Vinmec, Vinschool).
- Từ chối lịch sự nếu khách hàng hỏi về các thương hiệu khác hoặc các chủ đề không liên quan.

## 5. OUTPUT CONTRACT (ReAct Format)
Khi suy luận và hành động, hãy tuân theo cấu trúc:
Thought: Phân tích yêu cầu của người dùng và quyết định hành động.
Action: Tên công cụ cần gọi [search_product_catalog | submit_support_ticket] (nếu cần).
Action Input: Tham số đầu vào dạng JSON (nếu cần).
Observation: Kết quả trả về từ công cụ.
Final Answer: Câu trả lời cuối cùng gửi tới người dùng.
"""



# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        iteration = 1

        # TODO 3: Phân tích intent từ user_input
        #   - Xác định cần gọi tool nào (catalog? ticket? cả hai? FAQ?)
        #   - Gợi ý: Dùng keyword matching hoặc regex
        user_lower = user_input.lower()

        # 1. Phát hiện FAQ
        is_faq = "bảo hành" in user_lower or "chính sách" in user_lower

        # 2. Phát hiện Ticket
        needs_ticket = any(kw in user_lower for kw in ["lỗi", "sự cố", "hỏng", "adas", "hỗ trợ gấp", "nghiêm trọng", "tôi tên"])
        
        # 3. Phát hiện Catalog
        needs_catalog = any(kw in user_lower for kw in ["xe", "ô tô", "vf", "du lịch", "resort", "vinpearl", "giá dưới", "triệu"])


        # TODO 4: Xây dựng Agent Loop (while iteration <= self.max_iterations)
        #   - Iteration 1: Gọi tool #1 nếu cần (search_product_catalog)
        if is_faq:
            self.trace.append({
                "step": "thought",
                "thought": "Câu hỏi thuộc chính sách bảo hành, trả lời trực tiếp mà không cần tool."
            })
            answer = "Chính sách bảo hành pin xe điện VinFast kéo dài lên tới 10 năm hoặc 200.000 km tuỳ điều kiện nào đến trước."
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": iteration,
                "status": "completed"
            }

        #   - Iteration 2: Gọi tool #2 nếu cần (submit_support_ticket)
        if needs_ticket:
            self.trace.append({
                "step": "thought",
                "thought": "Khách hàng gặp sự cố, cần gọi tool submit_support_ticket."
            })
            
            # Trích xuất tên
            name_match = re.search(r"(?:tôi tên là|tôi tên)\s+([^,\.]+)", user_input, re.IGNORECASE)
            customer_name = name_match.group(1).strip() if name_match else "Khách hàng"
            
            # Trích xuất mức độ ưu tiên
            priority = "high" if any(w in user_lower for w in ["gấp", "nghiêm trọng", "khẩn cấp"]) else "medium"
            
            # Gọi tool
            ticket_res = submit_support_ticket(
                customer_name=customer_name,
                issue_description=user_input,
                priority=priority
            )
            self.trace.append({
                "step": "tool_call",
                "tool": "submit_support_ticket",
                "result": ticket_res
            })
            
            answer = f"Yêu cầu của quý khách {ticket_res['customer_name']} đã được ghi nhận. Mã hỗ trợ: {ticket_res['ticket_id']} với mức độ ưu tiên {ticket_res['priority']}."
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": iteration,
                "status": "completed"
            }
        #   - Iteration 3+: Tổng hợp Final Answer từ trace
        if needs_catalog:
            self.trace.append({
                "step": "thought",
                "thought": "Người dùng cần tìm kiếm sản phẩm, gọi tool search_product_catalog."
            })
            
            # Phân loại category
            category = "xe_dien" if any(w in user_lower for w in ["xe", "ô tô", "vf"]) else "du_lich"
            
            # Trích xuất max_price
            max_price = 999999999999
            price_match = re.search(r"(\d+)\s*triệu", user_lower)
            if price_match:
                max_price = int(price_match.group(1)) * 1_000_000
            
            # Gọi tool
            products = search_product_catalog(category=category, max_price=max_price)
            self.trace.append({
                "step": "tool_call",
                "tool": "search_product_catalog",
                "args": {"category": category, "max_price": max_price},
                "result": products
            })
            # Edge case: Không tìm thấy sản phẩm phù hợp
            if not products or len(products) == 0:
                answer = "Rất tiếc, chúng tôi không tìm thấy sản phẩm nào phù hợp với tầm giá bạn yêu cầu."
            else:
                product_names = [f"{p['name']} ({p['price_vnd']:,} VNĐ)" for p in products]
                answer = f"Các sản phẩm phù hợp với yêu cầu của bạn: {', '.join(product_names)}."
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": iteration,
                "status": "completed"
            }
        # Fallback mặc định
        return {
            "answer": "Rất tiếc, tôi chưa hiểu rõ yêu cầu của bạn.",
            "trace": self.trace,
            "iterations": iteration,
            "status": "completed"
        }

        #   - Lưu mỗi bước vào self.trace
        
# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
