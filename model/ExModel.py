import gurobipy as gp
from gurobipy import GRB

# Dữ liệu được khởi tạo tôí giản cho dễ xử lý
warehouses = range(3)  # Giả sử có 3 kho
retailers = range(4)  # Giả sử có 4 điểm tiêu thụ

# Chi phí vận chuyển
cost = [
    [2, 3, 1, 4],
    [5, 4, 2, 3],
    [3, 2, 5, 1]
]

# Số lượng hàng hóa có sẵn tại mỗi kho
supply = [100, 150, 200]

# Nhu cầu hàng hóa tại mỗi điểm tiêu thụ
demand = [80, 120, 100, 50]

# Tạo mô hình
model = gp.Model("Distribution")

# DATA CODE GOES HERE

# Tạo biến số
x = model.addVars(warehouses, retailers, name="x", vtype=GRB.CONTINUOUS, lb=0)

# Thiết lập hàm mục tiêu
model.setObjective(gp.quicksum(cost[i][j] * x[i, j] for i in warehouses for j in retailers), GRB.MINIMIZE)

# Thêm ràng buộc về cung ứng
model.addConstrs((gp.quicksum(x[i, j] for j in retailers) <= supply[i] for i in warehouses), "Supply")

# Thêm ràng buộc về nhu cầu
model.addConstrs((gp.quicksum(x[i, j] for i in warehouses) >= demand[j] for j in retailers), "Demand")


# Tối ưu hóa mô hình
model.optimize()

m = model

# CONSTRAINT CODE GOES HERE

# Solve
m.update()
model.optimize()

# In kết quả
if m.status == GRB.OPTIMAL:
    for i in warehouses:
        for j in retailers:
            if x[i, j].x > 0:
                print(
                    f"Vận chuyển {x[i, j].x} đơn vị hàng hóa từ kho {i} đến điểm tiêu thụ {j} với chi phí {cost[i][j]} mỗi đơn vị.")
else:
    print("Không tìm thấy lời giải tối ưu.")
