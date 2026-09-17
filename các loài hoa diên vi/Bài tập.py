import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# 1. Đọc dữ liệu từ file
df = pd.read_csv("e:/Học máy nâng cao/các loài hoa diên vi/Iris.csv")

# 2. Tiền xử lý dữ liệu: Loại bỏ cột 'Id' nếu có vì nó không có giá trị trong việc phân loại
if 'Id' in df.columns:
    df = df.drop('Id', axis=1)

# 3. Trực quan hóa dữ liệu
# Thiết lập phong cách giao diện cơ bản
sns.set_theme(style="ticks")

# Tạo biểu đồ pairplot, phân loại màu sắc và hình dáng theo cột 'Species'
g = sns.pairplot(df, hue="Species", markers=["o", "s", "D"])

# Điều chỉnh khoảng cách lề trên để nhường chỗ cho tiêu đề
plt.subplots_adjust(top=0.95)
g.fig.suptitle('Biểu đồ phân tán và phân phối các đặc trưng của hoa Iris', fontsize=16)

plt.savefig('iris_pairplot.png', dpi=300, bbox_inches='tight')

# Hiển thị biểu đồ 
plt.show()

# 4. In ra bảng thống kê giá trị trung bình của từng đặc trưng theo loài hoa
print("Bảng giá trị trung bình các đặc trưng theo loài:")
print(df.groupby('Species').mean())