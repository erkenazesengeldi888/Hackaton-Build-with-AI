# Тестовые сценарии и фактические ответы системы

_Ответы получены автоматически (расчётное время запроса: 2026-10-18 19:00, Астана). Режим без LLM (шаблон); с `GEMINI_API_KEY` тот же контекст отдаётся Gemini. Настройки по умолчанию: радиус 2 км, в выдаче места с оценкой 2GIS. Время суток учитывается при ранжировании: места, не работающие по известным часам, понижаются._

## Сценарий 1 (пользовательский)

**Вход:** «Популярное кафе с видом на город»  
**Контекст:** я возле «Байтерек», времени 90 мин, компания 1 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='rec'><div class='rec-h'>1. Kök Grand View <span>1.66 км · 22 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>Вид на город с 21-го этажа; 5.0 из 5, но оценок всего 49 <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~60 мин на месте · с дорогой 104 из 90 мин — не хватит времени</span></div><div class='kv'><span class='k'>Что делать</span><span>Столик у окна к закату — кадр с панорамой города <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>2. Mokki <span>0.42 км · 6 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>Вид на город с 3-го этажа; 4.9 из 5, 1888 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~60 мин на месте · с дорогой 72 из 90 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Столик у окна к закату — кадр с панорамой города <small class='src idea'>идея</small></span></div></div>

## Сценарий 2 (пользовательский)

**Вход:** «Хочу что-то связанное с адреналином»  
**Контекст:** я возле «Хан Шатыр», времени 120 мин, компания 3 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='rec'><div class='rec-h'>1. Fire Drift <span>0.83 км · 11 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>Картинг и дрифт; 4.9 из 5, 97 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~75 мин на месте · с дорогой 97 из 120 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Заезд на время: кто быстрее — тот выбирает десерт <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>2. Ailand <span>1.96 км · 26 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 26351 оценок<i class='nd'> · нет данных: адреналин</i> <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~75 мин на месте · с дорогой 127 из 120 мин — не хватит времени</span></div><div class='kv'><span class='k'>Что делать</span><span>Заезд на время: кто быстрее — тот выбирает десерт <small class='src idea'>идея</small></span></div></div>
> <div class='meta'>Для компании из 3: бронируйте заранее.</div>

## Сценарий 3 (пользовательский)

**Вход:** «Места, где можно прийти с собакой»  
**Контекст:** я возле «EXPO», времени 90 мин, компания 1 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='meta'>Подтверждённого места нет — ниже ближайшие варианты, проверьте перед визитом.</div>
> <div class='rec'><div class='rec-h'>1. Ботанический сад <span>1.86 км · 25 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 31919 оценок<i class='nd'> · нет данных: можно с собакой</i> <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~40 мин на месте · с дорогой 90 из 90 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Прогулка с питомцем: поводок, пакеты, вода <small class='src idea'>идея</small></span></div></div>

## Сценарий 4 (из ТЗ)

**Вход:** «Я сейчас возле Mega Silk Way, хочу прогуляться 30–60 минут — что посоветуете?»  
**Контекст:** я возле «Mega Silk Way», времени 60 мин, компания 1 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> В радиусе поиска нет подходящих мест в базе. Увеличьте радиус или уберите фильтры.

## Сценарий 5 (из ТЗ)

**Вход:** «Хочу тихое место с кофе и розеткой недалеко от меня»  
**Контекст:** я возле «Mega Silk Way», времени 60 мин, компания 1 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='meta'>Подтверждённого места нет — ниже ближайшие варианты, проверьте перед визитом.</div>
> <div class='rec'><div class='rec-h'>1. Drinkit <span>0.0 км · 1 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 521 оценок<i class='nd'> · нет данных: тихое место, розетки</i> <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~30 мин на месте · с дорогой 32 из 60 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Кофе и десерт; для работы — розетки и wi-fi <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>2. Starbucks <span>0.0 км · 1 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.4 из 5, 867 оценок<i class='nd'> · нет данных: тихое место, розетки</i> <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~30 мин на месте · с дорогой 32 из 60 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Кофе и десерт; для работы — розетки и wi-fi <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>3. Noble <span>1.6 км · 21 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 447 оценок<i class='nd'> · нет данных: тихое место, розетки</i> <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~30 мин на месте · с дорогой 72 из 60 мин — не хватит времени</span></div><div class='kv'><span class='k'>Что делать</span><span>Кофе и десерт; для работы — розетки и wi-fi <small class='src idea'>идея</small></span></div></div>

## Сценарий 6 (из ТЗ)

**Вход:** «Еду с ребёнком — где рядом есть детские площадки или музеи с интерактивами?»  
**Контекст:** я возле «Байтерек», времени 120 мин, компания 3 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> В радиусе поиска нет подходящих мест в базе. Увеличьте радиус или уберите фильтры.

## Сценарий 7 (из ТЗ)

**Вход:** «Я турист, у меня 2 часа перед вылетом: что можно посмотреть поблизости?»  
**Контекст:** я возле «Байтерек», времени 120 мин, компания 1 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='rec'><div class='rec-h'>1. Хан Шатыр <span>1.92 км · 26 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 105814 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~45 мин на месте · с дорогой 97 из 120 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Прогулка, кофе и кино под одной крышей <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>2. Астана Опера <span>1.59 км · 21 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>5.0 из 5, 6708 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~120 мин на месте · с дорогой 162 из 120 мин — не хватит времени</span></div><div class='kv'><span class='k'>Что делать</span><span>Спектакль; афиша и билеты заранее <small class='src idea'>идея</small></span></div></div>

## Сценарий 8 (из ТЗ)

**Вход:** «Ищу необычную ночную активность (последние пару часов)»  
**Контекст:** я возле «Хан Шатыр», времени 120 мин, компания 2 чел.

**Ожидаемый тип ответа:** 1–3 пункта: почему подходит, что делать, источник данных, честные пометки о том, чего в данных нет.

**Фактический ответ:**

> <div class='rec'><div class='rec-h'>1. Brewery <span>0.47 км · 6 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.8 из 5, 1218 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~60 мин на месте · с дорогой 72 из 120 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Коктейли и музыка; уточните бронь <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>2. Ailand <span>1.96 км · 26 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 26351 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~75 мин на месте · с дорогой 127 из 120 мин — не хватит времени</span></div><div class='kv'><span class='k'>Что делать</span><span>Активность на выбор; бронь и ограничения <small class='src idea'>идея</small></span></div></div>
> <div class='rec'><div class='rec-h'>3. Fire Drift <span>0.83 км · 11 мин пешком</span></div><div class='kv'><span class='k'>Почему</span><span>4.9 из 5, 97 оценок <small class='src data'>данные POI</small></span></div><div class='kv'><span class='k'>Время</span><span>~75 мин на месте · с дорогой 97 из 120 мин — успеваете</span></div><div class='kv'><span class='k'>Что делать</span><span>Активность на выбор; бронь и ограничения <small class='src idea'>идея</small></span></div></div>
