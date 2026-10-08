-- Session-level funnel: sessions → added to cart → purchased, by channel
-- Source: bigquery-public-data.thelook_ecommerce.events
--
-- NOTE: events.traffic_source is a different field/taxonomy than
-- users.traffic_source used in weekly_channel_performance.sql — they
-- share some channel names (Email, Organic, Facebook) but are not the
-- same dimension and should not be joined or compared directly.

WITH session_stages AS (
  SELECT
    session_id,
    traffic_source,
    MAX(event_type = 'cart')     AS added_to_cart,
    MAX(event_type = 'purchase') AS purchased
  FROM `bigquery-public-data.thelook_ecommerce.events`
  WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL @weeks_back WEEK)
  GROUP BY session_id, traffic_source
)
SELECT
  traffic_source AS channel,
  COUNT(*)                             AS sessions,
  COUNTIF(added_to_cart)               AS added_to_cart,
  COUNTIF(added_to_cart AND purchased) AS purchased
FROM session_stages
GROUP BY channel
ORDER BY sessions DESC;