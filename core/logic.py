def calculate_letter_grade(score, avg, std):
    """T-Skoru üzerinden harf notu tahmini yapar (İTÜ Standart)."""
    try:
        score = float(str(score).replace(",", "."))
        avg = float(str(avg).replace(",", "."))
        std = float(str(std).replace(",", "."))

        if std == 0:
            return "Bilinmiyor (Sapma 0)"

        t_score = 10 * (score - avg) / std + 50

        if t_score >= 60:
            return "AA (4.00)"
        elif t_score >= 57.5:
            return "BA+ (3.75)"
        elif t_score >= 55:
            return "BA (3.50)"
        elif t_score >= 52.5:
            return "BB+ (3.25)"
        elif t_score >= 50:
            return "BB (3.00)"
        elif t_score >= 47.5:
            return "CB+ (2.75)"
        elif t_score >= 45:
            return "CB (2.50)"
        elif t_score >= 42.5:
            return "CC+ (2.25)"
        elif t_score >= 40:
            return "CC (2.00)"
        elif t_score >= 37.5:
            return "DC+ (1.75)"
        elif t_score >= 35:
            return "DC (1.50)"
        elif t_score >= 32.5:
            return "DD+ (1.25)"
        elif t_score >= 30:
            return "DD (1.00)"
        else:
            return "FF (0.00)"
    except Exception:
        return None


def predict_course_performance(course_data):
    """Dersin genel ortalamasını ve harf notu tahminini hesaplar."""
    grades = course_data.get("grades", {})
    if not grades:
        return None

    total_weighted_score = 0
    total_class_weighted_score = 0
    total_weight = 0
    simple_sum = 0
    simple_class_sum = 0
    count = 0
    class_count = 0

    # Atlanacak anahtar kelimeler (Özet satırları)
    skip_keywords = ["ortal", "başarı notu", "toplam", "geçme notu"]

    for key, entry in grades.items():
        # Özet satırlarını hesaplamaya dahil etme
        if any(kw in key.lower() for kw in skip_keywords):
            continue

        try:
            val = float(str(entry["not"]).replace(",", "."))
            detay = entry.get("detaylar", {})
            class_avg_str = detay.get("Ortalama")
            class_avg = (
                float(str(class_avg_str).replace(",", ".")) if class_avg_str else None
            )

            weight_str = (
                entry.get("agirlik", "").replace("%", "").replace(",", ".").strip()
            )

            try:
                weight = float(weight_str) if weight_str else 0
                if weight > 0:
                    total_weighted_score += val * (weight / 100)
                    if class_avg is not None:
                        total_class_weighted_score += class_avg * (weight / 100)
                    total_weight += weight
                else:
                    simple_sum += val
                    if class_avg is not None:
                        simple_class_sum += class_avg
                        class_count += 1
                    count += 1
            except ValueError:
                simple_sum += val
                if class_avg is not None:
                    simple_class_sum += class_avg
                    class_count += 1
                count += 1
        except Exception:
            continue

    result = {}
    if total_weight > 0:
        result["current_avg"] = total_weighted_score / (total_weight / 100)
        # Sınıf ortalaması sadece tüm girilen notların ortalaması varsa anlamlıdır
        # Ancak kısmi bilgi de verebiliriz.
        if total_class_weighted_score > 0:
            result["class_avg"] = total_class_weighted_score / (total_weight / 100)
        result["total_weight_entered"] = total_weight
    elif count > 0:
        result["current_avg"] = simple_sum / count
        if class_count > 0:
            result["class_avg"] = simple_class_sum / class_count
        result["total_weight_entered"] = 0

    # Harf notu tahmini için istatistiği olan en son sınavı bul
    last_valid_exam = None
    for key, entry in reversed(list(grades.items())):
        if any(kw in key.lower() for kw in skip_keywords):
            continue
        detay = entry.get("detaylar", {})
        if detay.get("Ortalama") and detay.get("Std. Sapma"):
            last_valid_exam = entry
            break

    if last_valid_exam:
        detay = last_valid_exam.get("detaylar", {})
        predicted = calculate_letter_grade(
            result.get("current_avg", 0), detay["Ortalama"], detay["Std. Sapma"]
        )
        if predicted:
            result["predicted_letter"] = predicted

    return result
