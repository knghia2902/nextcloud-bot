# 📚 Commands System Guide

## 🎯 Tổng Quan

Commands System cho phép tạo và quản lý các lệnh bot với điều kiện phức tạp. Hệ thống hỗ trợ nhiều loại điều kiện để kiểm soát khi nào command được thực thi.

## 🚀 Cách Sử Dụng

### 1. Truy Cập Commands Management
- Mở web interface: `http://localhost:3000/commands`
- Đăng nhập với tài khoản admin
- Click "Add Command with Conditions"

### 2. Tạo Command Cơ Bản

#### Bước 1: Thông Tin Command
```
Command Name: dinhchi
Description: Đình chỉ nhân viên
Scope: Global (áp dụng cho tất cả)
```

#### Bước 2: Bot Response
```
🚫 ĐÌNH CHỈ NHÂN VIÊN

👤 Mã nhân viên: {first_arg}
⚠️ Trạng thái: Đang đình chỉ
👮 Thực hiện bởi: admin
🕒 Thời gian: {current_time}

📋 Lưu ý: Nhân viên đã được đình chỉ và không thể truy cập hệ thống.
```

## 📋 Các Loại Điều Kiện

### 1. 📝 Message Content Rules

#### A. Số Ký Tự Bắt Buộc
- **Mục đích:** Kiểm tra độ dài tham số command
- **Ví dụ:** Mã nhân viên phải có đúng 11 ký tự
- **Cách dùng:**
  ```
  ✅ Enable: Số ký tự bắt buộc
  Số ký tự: 11
  Mô tả: Mã nhân viên phải có đúng 11 ký tự
  ```

#### B. Ký Tự Bắt Buộc
- **Mục đích:** Kiểm tra ký tự bắt đầu
- **Ví dụ:** Mã nhân viên phải bắt đầu bằng O5A hoặc O5B
- **Cách dùng:**
  ```
  ✅ Enable: Ký tự bắt buộc
  Ký tự bắt đầu: O5A,O5B
  Mô tả: Mã phải bắt đầu bằng O5A hoặc O5B
  ```

#### C. Kiểm Tra Tham Số Command (Nâng Cao)
- **Mục đích:** Sử dụng regex pattern phức tạp
- **Ví dụ:** Pattern `^(O5A|O5B).{8}$`
- **Cách dùng:**
  ```
  ✅ Enable: Kiểm tra tham số command
  Pattern: ^(O5A|O5B).{8}$
  Mô tả: Kiểm tra mã nhân viên
  ```

### 2. 🕐 Time Conditions
- **Mục đích:** Giới hạn thời gian sử dụng command
- **Ví dụ:** Chỉ cho phép từ 9:00 - 17:00
- **Cách dùng:**
  ```
  ✅ Enable time range restriction
  Start Time: 09:00
  End Time: 17:00
  ```

### 3. 📅 Day of Week
- **Mục đích:** Giới hạn ngày trong tuần
- **Ví dụ:** Chỉ cho phép thứ 2-6
- **Cách dùng:** Check các ngày cho phép

### 4. ✅ Required Words
- **Mục đích:** Từ bắt buộc phải có trong message
- **Ví dụ:** urgent, important
- **Cách dùng:** Nhập từ cách nhau bằng dấu phẩy

### 5. ❌ Forbidden Words
- **Mục đích:** Từ cấm không được có
- **Ví dụ:** spam, test, fake
- **Cách dùng:** Nhập từ cách nhau bằng dấu phẩy

### 6. ⏱️ Cooldown
- **Mục đích:** Thời gian chờ giữa các lần sử dụng
- **Ví dụ:** 60 giây
- **Cách dùng:** Nhập số giây

## 🧪 Test Commands

### Cách Test Command
1. Tìm command trong danh sách
2. Click nút Test (🧪)
3. Nhập thông tin test:
   - **Test User ID:** ID người dùng test
   - **Test Room ID:** ID phòng test
   - **Test Message:** Tin nhắn đầy đủ (ví dụ: `!dinhchi O5A12345678`)
4. Click "Run Test"

### Ví Dụ Test Command !dinhchi

#### Test Thành Công:
```
Test Message: !dinhchi O5A12345678
Kết quả: ✅ PASS
- character_length: ✅ PASS (11 ký tự)
- required_characters: ✅ PASS (bắt đầu O5A)
```

#### Test Thất Bại:
```
Test Message: !dinhchi 19216811
Kết quả: ❌ FAIL
- character_length: ✅ PASS (8 ký tự, cần 11)
- required_characters: ❌ FAIL (bắt đầu 19, cần O5A/O5B)
```

## 📊 Variables Trong Response

### Các Variables Có Sẵn:
- `{user_id}` - ID người dùng
- `{room_id}` - ID phòng
- `{current_time}` - Thời gian hiện tại
- `{message}` - Tin nhắn đầy đủ
- `{first_arg}` - Tham số đầu tiên của command

### Ví Dụ Sử Dụng:
```
🚫 ĐÌNH CHỈ NHÂN VIÊN

👤 Mã nhân viên: {first_arg}
👮 Thực hiện bởi: {user_id}
🕒 Thời gian: {current_time}
🏠 Phòng: {room_id}
```

## 🎯 Ví Dụ Thực Tế: Command !dinhchi

### Yêu Cầu:
- Command: `!dinhchi 19216811`
- Mã nhân viên phải bắt đầu bằng O5A hoặc O5B
- Mã nhân viên phải có đúng 11 ký tự

### Cấu Hình:
1. **Command Name:** `dinhchi`
2. **Conditions:**
   - ✅ Số ký tự bắt buộc: 11
   - ✅ Ký tự bắt buộc: O5A,O5B
3. **Response:** Sử dụng `{first_arg}` để hiển thị mã nhân viên

### Test Cases:
- ✅ `!dinhchi O5A12345678` - PASS
- ✅ `!dinhchi O5B87654321` - PASS  
- ❌ `!dinhchi 19216811` - FAIL (không bắt đầu O5A/O5B)
- ❌ `!dinhchi O5A123` - FAIL (chỉ 6 ký tự)

## 🔧 Troubleshooting

### Command Không Hoạt Động:
1. Kiểm tra command có enabled không
2. Test conditions với tool test
3. Xem logs trong console
4. Kiểm tra format message đúng chưa

### Test Thất Bại:
1. Kiểm tra điều kiện có đúng không
2. Xem chi tiết lỗi trong test results
3. Điều chỉnh conditions cho phù hợp

## 📈 Best Practices

1. **Đặt tên command rõ ràng:** `dinhchi`, `capnhat`, `thongbao`
2. **Mô tả đầy đủ:** Giải thích rõ command làm gì
3. **Test kỹ lưỡng:** Test cả trường hợp pass và fail
4. **Sử dụng variables:** Làm response động và hữu ích
5. **Điều kiện hợp lý:** Không quá phức tạp, dễ hiểu

## 🚀 Advanced Features

### Scope Management:
- **Global:** Áp dụng cho tất cả
- **Room:** Chỉ áp dụng cho phòng cụ thể  
- **User:** Chỉ áp dụng cho user cụ thể

### Command Actions:
- **Edit:** Chỉnh sửa command và conditions
- **Test:** Test điều kiện command
- **Delete:** Xóa command
- **Toggle:** Bật/tắt command

---

📝 **Lưu ý:** Hướng dẫn này được cập nhật liên tục. Kiểm tra phiên bản mới nhất tại `/docs/COMMANDS_GUIDE.md`
