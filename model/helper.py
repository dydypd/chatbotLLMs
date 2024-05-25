import matplotlib.pyplot as plt


def visualize_solution(facility_coords, customer_coords, open_facilities, assignments):
    plt.figure(figsize=(10, 6))

    # Vẽ các cơ sở
    for facility, (x, y) in facility_coords.items():
        if facility in open_facilities:
            plt.scatter(x, y, color='green', s=200, marker='s',
                        label='Open Facility' if facility == open_facilities[0] else "")
        else:
            plt.scatter(x, y, color='red', s=200, marker='s',
                        label='Closed Facility' if facility == list(facility_coords.keys())[0] else "")
        plt.text(x, y, f'{facility}', fontsize=12, ha='right')

    # Vẽ các khách hàng
    for customer, (x, y) in customer_coords.items():
        plt.scatter(x, y, color='blue', s=100, marker='o',
                    label='Customer' if customer == list(customer_coords.keys())[0] else "")
        plt.text(x, y, f'{customer}', fontsize=12, ha='left')

    # Vẽ các đường kết nối
    for facility, customers in assignments.items():
        for customer in customers:
            fx, fy = facility_coords[facility]
            cx, cy = customer_coords[customer]
            plt.plot([fx, cx], [fy, cy], color='black', linestyle='--', linewidth=1)

    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.title('Facility Location and Customer Assignments')
    plt.legend(loc='upper right')
    plt.grid(True)
    plt.show()
