import re
from typing import Dict, List, Optional, Union

from autogen.agentchat import AssistantAgent
from autogen.agentchat.agent import Agent
from autogen.code_utils import extract_code
from eventlet.timeout import Timeout
from termcolor import colored

try:
    from gurobipy import GRB
except Exception:
    print("Note: Gurobi not loaded")

# %% Prompt để gửi cho agent
# Cần giải thch cho agent hiểu được vấn đề cụ thể cần giải quyết.

WRITER_SYSTEM_MSG = """You are a chatbot to:
(1) write Python code to answer users questions for supply chain-related coding
project;
(2) explain solutions from a {solver_software} Python solver.

--- SOURCE CODE ---
{source_code}

--- DOC STR ---
{doc_str}
---

Here are some example questions and their answers and codes:
--- EXAMPLES ---
{example_qa}
---

The execution result of the original source code is below.
--- Original Result ---
{execution_result}

Note that your written code will be added to the lines with substring:
"#  *** CODE GOES HERE"
So, you don't need to write other code, such as m.optimize() or m.update().
You just need to write code snippet in ```python ...``` block.

Be mindful that order of the code, because some variables might not be defined
yet when your code is inserted into the source code.
"""

SAFEGUARD_SYSTEM_MSG = """
Given the original source code:
{source_code}

Is the following code safe (not malicious code to break security,
privacy, or hack the system) to run?
Answer only one word.
If not safe, answer `DANGER`; else, answer `SAFE`.
"""

# %% Tham số để agent tìm kiếm và thay thế code trong source code
DATA_CODE_STR = "# DATA CODE GOES HERE"
CONSTRAINT_CODE_STR = "# CONSTRAINT CODE GOES HERE"


# %% Agent chính
class GPTAgent(AssistantAgent):
    """
    Agent này duy trì 2 agent phụ:
    - writer: để viết code
    - safeguard: để kiểm tra code có an toàn không
    """

    def __init__(self,
                 name,
                 source_code,
                 solver_software="gurobi",
                 doc_str="",
                 example_qa="",
                 debug_times=3,
                 use_safeguard=True,
                 **kwargs):
        """
        Args:
            name (str): Tên của agent.
            source_code (str): Mã nguồn của agent.
            solver_software (str): Tên của solver software.
            doc_str (str): Mô tả về source code.
            example_qa (str): Ví dụ về câu hỏi và câu trả lời.
            debug_times (int): Số lần debug.
            use_safeguard (bool): Sử dụng safeguard hay không.
            **kwargs: Các tham số khác.
        """
        assert source_code.find(DATA_CODE_STR) >= 0, "DATA_CODE_STR not found."
        assert source_code.find(
            CONSTRAINT_CODE_STR) >= 0, "CONSTRAINT_CODE_STR not found."

        super().__init__(name, **kwargs)
        self._source_code = source_code
        self._doc_str = doc_str
        self._example_qa = example_qa
        self._solver_software = solver_software
        self._origin_execution_result = _run_with_exec(source_code,
                                                       self._solver_software)
        self._writer = AssistantAgent("writer", llm_config=self.llm_config)
        self._safeguard = AssistantAgent("safeguard",
                                         llm_config=self.llm_config)
        self._debug_times_left = self.debug_times = debug_times
        self._use_safeguard = use_safeguard
        self._success = False

    def generate_reply(
            self,
            messages: Optional[List[Dict]] = None,
            default_reply: Optional[Union[str, Dict]] = "",
            sender: Optional[Agent] = None,
    ) -> Union[str, Dict, None]:
        """
        Tạo phản hồi dựa trên lịch sử trò chuyện.
        :param messages:
        :param default_reply:
        :param sender:
        :return:
        """

        del messages, default_reply
        # Nếu sender không phải là writer hoặc safeguard, thì đó là người dùng.
        if sender not in [self._writer, self._safeguard]:
            # Step 1: Nhận câu hỏi từ người dùng
            user_chat_history = ("\nHere are the history of discussions:\n"
                                 f"{self._oai_messages[sender]}")
            writer_sys_msg = (WRITER_SYSTEM_MSG.format(
                solver_software=self._solver_software,
                source_code=self._source_code,
                doc_str=self._doc_str,
                example_qa=self._example_qa,
                execution_result=self._origin_execution_result,
            ) + user_chat_history)
            safeguard_sys_msg = SAFEGUARD_SYSTEM_MSG.format(
                source_code=self._source_code) + user_chat_history
            self._writer.update_system_message(writer_sys_msg)
            self._safeguard.update_system_message(safeguard_sys_msg)
            self._writer.reset()
            self._safeguard.reset()
            self._debug_times_left = self.debug_times
            self._success = False
            # Step 2: Gửi code cho writer và safeguard
            self.initiate_chat(self._writer, message=CODE_PROMPT)
            if self._success:
                # Nhận câu trả lời từ writer
                reply = self.last_message(self._writer)["content"]
            else:
                reply = "Sorry. I cannot answer your question."
            # Gửi câu trả lời cho người dùng
            return reply
        if sender == self._writer:
            # nếu sender là writer, thì gửi câu hỏi cho safeguard
            return self._generate_reply_to_writer(sender)

    def _generate_reply_to_writer(self, sender):
        """Tạo câu trả lời cho writer.
        sender: là writer."""
        # nếu thành công, không cần trả lời cho writer
        if self._success:
            # no reply to writer
            return

        _, code = extract_code(self.last_message(sender)["content"])[0]

        # Kiểm tra code có an toàn không
        safe_msg = ""
        if self._use_safeguard:
            self.initiate_chat(message=SAFEGUARD_PROMPT.format(code=code),
                               recipient=self._safeguard)
            safe_msg = self.last_message(self._safeguard)["content"]
        else:
            safe_msg = "SAFE"

        if safe_msg.find("DANGER") < 0:
            src_code = _insert_code(self._source_code, code,
                                    self._solver_software)
            execution_rst = _run_with_exec(src_code, self._solver_software)
            print(colored(str(execution_rst), "yellow"))
            if type(execution_rst) in [str, int, float]:
                self._success = True
                return INTERPRETER_PROMPT.format(execution_rst=execution_rst)
        else:
            execution_rst = """
Sorry, this new code is not safe to run. I would not allow you to execute it.
Please try to find a new way (coding) to answer the question."""
        if self._debug_times_left > 0:
            # Try to debug and write code again (back to step 2)
            self._debug_times_left -= 1
            return DEBUG_PROMPT.format(error_type=type(execution_rst),
                                       error_message=str(execution_rst))


def _run_with_exec(src_code: str,
                   solver_software: str) -> Union[str, Exception]:
    """Chạy src_code và trả về kết quả tối ưu.
    src_code: là mã nguồn cần chạy.
    solver_software: là tên của solver software.
    """
    # Tạo một biến locals_dict để chạy code
    # locals_dict sẽ chứa các biến globals() và locals() sau khi chạy code.
    locals_dict = {}
    locals_dict.update(globals())
    locals_dict.update(locals())
    # Thực thi src_code trong một thời gian nhất định.
    # Nếu src_code chạy quá thời gian timeout, sẽ trả về TimeoutError.
    timeout = Timeout(
        60,
        TimeoutError("This is a timeout exception, in case "
                     "GPT's code falls into infinite loop."))
    try:
        exec(src_code, locals_dict, locals_dict)
    except Exception as e:
        return e
    finally:
        timeout.cancel()

    # Lấy kết quả tối ưu từ locals_dict
    try:
        ans = _get_optimization_result(locals_dict, solver_software)
    except Exception as e:
        return e

    return ans


def _replace(src_code: str, old_code: str, new_code: str) -> str:
    """Thay thế old_code bằng new_code trong src_code.
    old_code: là chuỗi cần thay thế.
    new_code: là chuỗi mới thay thế vào src_code.
    """
    pattern = r"( *){old_code}".format(old_code=old_code)
    head_spaces = re.search(pattern, src_code, flags=re.DOTALL).group(1)
    new_code = "\n".join([head_spaces + line for line in new_code.split("\n")])
    rst = re.sub(pattern, new_code, src_code)
    return rst


def _insert_code(src_code: str, new_lines: str, solver_software: str) -> str:
    """Chèn code mới vào src_code tại vị trí của old_code.
    old_code: là chuỗi cần thay thế.
    new_lines: là chuỗi code mới cần chèn vào src_code.
    Nếu solver software là gurobi, thì chèn new_lines vào vị trí của CONSTRAINT_CODE_STR.
    Ngược lại, không làm gì"""
    if solver_software == "gurobi":
        if new_lines.find("addConstr") >= 0:
            return _replace(src_code, CONSTRAINT_CODE_STR, new_lines)
    else:
        return ""

    return _replace(src_code, DATA_CODE_STR, new_lines)


def _get_optimization_result(locals_dict: dict, solver_software: str) -> str:
    """Lấy kết quả tối ưu từ locals_dict sau khi chạy code.
    locals_dict: là biến locals() sau khi chạy code.
    solver_software: là tên của solver software.
    """
    if solver_software == "gurobi":
        status = locals_dict["m"].Status
        if status != GRB.OPTIMAL:
            if status == GRB.UNBOUNDED:
                ans = "unbounded"
            elif status == GRB.INF_OR_UNBD:
                ans = "inf_or_unbound"
            elif status == GRB.INFEASIBLE:
                ans = "infeasible"
                m = locals_dict["m"]
                m.computeIIS()
                constrs = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
                ans += "\nConflicting Constraints:\n" + str(constrs)
            else:
                ans = "Model Status:" + str(status)
        else:
            ans = "Optimization problem solved. The objective value is: " + str(
                locals_dict["m"].objVal)
    else:
        raise ValueError("Unknown solver software: " + solver_software)

    return ans


# %% Prompts để gửi cho người dùng và cho agent
CODE_PROMPT = """
Answer Code:
"""

DEBUG_PROMPT = """

While running the code you suggested, I encountered the {error_type}:
--- ERROR MESSAGE ---
{error_message}

Please try to resolve this bug, and rewrite the code snippet.
--- NEW CODE ---
"""

SAFEGUARD_PROMPT = """
--- Code ---
{code}

--- One-Word Answer: SAFE or DANGER ---
"""

INTERPRETER_PROMPT = """Here are the execution results: {execution_rst}

Can you organize these information to a human readable answer?
Remember to compare the new results to the original results you obtained in the
beginning.

--- HUMAN READABLE ANSWER ---
"""
