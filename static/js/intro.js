// PHẦN 5 — Giới thiệu: mẫu nhập, thẻ loài và hiệu ứng cánh hoa.
        const uploadedIrisSample = { "sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2 };
        // Kiểm tra đối tượng có đủ bốn số đo rồi nạp vào biểu mẫu dự đoán.
        function applyUploadedSample(value) {
            if (!value || typeof value !== 'object' || Array.isArray(value) || features.some(k => typeof value[k] !== 'number' || !Number.isFinite(value[k]) || value[k] <= 0)) throw new Error('JSON phải có đủ 4 số đo dạng số, hữu hạn và lớn hơn 0.');
            features.forEach((k, i) => { $(shortIds[i] + '_input').value = value[k]; const range = $(shortIds[i] + '_range'); range.min = Math.min(Number(range.min), value[k]); range.max = Math.max(Number(range.max), value[k]); range.value = value[k] });
        }
        // Chọn thẻ loài: đổi mô tả, trạng thái chọn và nạp mẫu minh họa.
        function selectIntroSpecies(i) { const samples = [[5.1, 3.5, 1.4, .2], [5.9, 3, 4.2, 1.5], [6.8, 3.2, 5.9, 2.3]]; const notes = ["Iris Setosa là một trong ba loài trong bộ dữ liệu Iris. Trong bộ dữ liệu này, Setosa có cánh hoa tương đối ngắn và hẹp, giúp phân biệt khá rõ với hai loài còn lại. Hệ thống sử dụng cả chiều dài và chiều rộng của đài hoa, cánh hoa để nhận diện; màu sắc trong ảnh chỉ giúp minh họa, không phải đầu vào của mô hình.", "Iris Versicolor là loài thứ hai trong bộ dữ liệu Iris. Kích thước cánh hoa thường nằm giữa Setosa và Virginica, nhưng một số mẫu có số đo gần với Virginica. Vì vậy, mô hình cần kết hợp cả bốn đặc trưng để phân loại. Bạn có thể chọn loài này để nạp mẫu và so sánh kết quả giữa năm thuật toán.", "Iris Virginica là loài thứ ba trong bộ dữ liệu Iris. Các mẫu thường có cánh hoa dài và rộng hơn Setosa, đồng thời có thể chồng lấn số đo với Versicolor. Đây là trường hợp hữu ích để quan sát sự khác nhau giữa các mô hình. Ảnh minh họa thể hiện loài hoa; dự đoán thực tế được tính từ bốn số đo bạn nhập."]; document.querySelectorAll('.species-pick').forEach((b, n) => { b.classList.toggle('selected', n === i); b.setAttribute('aria-pressed', String(n === i)) }); $('intro-species-note').textContent = notes[i] + ' Đã nạp mẫu minh họa vào trang Dự đoán.'; applyUploadedSample(Object.fromEntries(features.map((k, n) => [k, samples[i][n]]))) }
        // Khởi tạo mẫu mặc định và 12 cánh hoa trang Giới thiệu.
        document.addEventListener('DOMContentLoaded', () => {
            applyUploadedSample(uploadedIrisSample);
            for (let i = 0; i < 12; i++) { const p = document.createElement('span'); p.className = 'petal'; p.style.left = (i * 8 + 2) + '%'; p.style.animationDelay = (-i * 1.4) + 's'; p.style.animationDuration = (13 + i % 5) + 's'; $('sec-intro').append(p) }
        });
