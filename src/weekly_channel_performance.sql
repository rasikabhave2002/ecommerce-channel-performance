SELECT
  DATE_TRUNC(DATE(oi.created_at), WEEK(MONDAY)) AS week_start,
  u.traffic_source                              AS channel,
  COUNT(DISTINCT oi.order_id)                   AS orders,
  COUNT(DISTINCT oi.user_id)                    AS customers,
  ROUND(SUM(oi.sale_price), 2)                  AS revenue,
  ROUND(SUM(oi.sale_price) / COUNT(DISTINCT oi.order_id), 2) AS avg_order_value
FROM `bigquery-public-data.thelook_ecommerce.order_items` AS oi
JOIN `bigquery-public-data.thelook_ecommerce.users` AS u
  ON oi.user_id = u.id
WHERE
  oi.status NOT IN ('Cancelled', 'Returned')
  AND DATE(oi.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL @weeks_back WEEK)
GROUP BY week_start, channel
ORDER BY week_start, channel;