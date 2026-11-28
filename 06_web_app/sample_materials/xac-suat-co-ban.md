# Xác suất cơ bản cho AI Tutor

## Biến cố xung khắc

Hai biến cố A và B được gọi là xung khắc nếu không thể cùng xảy ra trong một phép thử. Khi đó P(A ∪ B) = P(A) + P(B). Nếu A và B có thể cùng xảy ra, công thức tổng quát là P(A ∪ B) = P(A) + P(B) − P(A ∩ B). Ta trừ xác suất phần giao vì phần đó đã được tính hai lần.

Ví dụ: gieo một xúc xắc cân bằng sáu mặt. Biến cố A là ra mặt 1 và biến cố B là ra mặt 6. Hai biến cố xung khắc, mỗi biến cố có xác suất 1/6, nên xác suất ra mặt 1 hoặc mặt 6 là 1/3.

## Biến cố đối

Biến cố đối của A gồm tất cả kết quả mà A không xảy ra. Xác suất của biến cố đối bằng 1 trừ xác suất của A. Khi đề bài hỏi xác suất có ít nhất một lần thành công, có thể tính xác suất không thành công lần nào rồi lấy 1 trừ đi kết quả đó.

Ví dụ: gieo hai đồng xu cân bằng độc lập. Xác suất không có mặt ngửa là 1/4, vì kết quả duy nhất thỏa mãn là cả hai đồng xu đều sấp. Vậy xác suất có ít nhất một mặt ngửa là 3/4.

## Biến cố độc lập

Hai biến cố A và B độc lập nếu việc một biến cố xảy ra không làm thay đổi xác suất của biến cố kia. Nếu A và B độc lập, xác suất cả hai cùng xảy ra bằng P(A) × P(B). Hai biến cố xung khắc có xác suất dương không độc lập, bởi việc biến cố thứ nhất xảy ra làm xác suất xảy ra biến cố thứ hai bằng 0.

Ví dụ: gieo xúc xắc cân bằng hai lần độc lập. Xác suất cả hai lần đều ra mặt 6 là (1/6) × (1/6) = 1/36.
