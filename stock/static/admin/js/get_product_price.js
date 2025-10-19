// Butun oyna (barcha elementlar) to'liq yuklanib bo'lishini kutamiz.
// Bu eng ishonchli usul.
window.onload = function() {
    // Hamma narsa yuklangach, Django'ning jQuery'si aniq tayyor bo'ladi.
    // Endi biz avvalgi, eng to'g'ri usuldan foydalanishimiz mumkin.
    (function($) {
        // Butun dokumentga "change" (o'zgarish) hodisasini bog'laymiz
        $(document).on('change', 'select[name^="items-"][name$="-product"]', function() {
            var productSelect = $(this); // Mahsulot tanlangan select maydoni
            var productId = productSelect.val(); // Tanlangan mahsulotning ID raqami

            // Qaysi qatordagi narx maydonini o'zgartirishni aniqlaymiz
            var priceInput = productSelect.closest('.dynamic-items').find('input[name$="-price"]');

            if (productId) {
                // Agar mahsulot tanlangan bo'lsa, API'ga so'rov yuboramiz
                $.ajax({
                    url: `/api/products/${productId}/price/`,
                    type: 'GET',
                    success: function(data) {
                        // Muvaffaqiyatli javob kelsa, narxni to'ldiramiz
                        priceInput.val(data.price);
                    },
                    error: function() {
                        console.error('Narxni olishda xatolik yuz berdi.');
                    }
                });
            } else {
                // Agar mahsulot tanlanmagan bo'lsa, narxni bo'shatamiz
                priceInput.val('');
            }
        });
    })(django.jQuery);
};