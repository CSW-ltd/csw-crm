# TLS va xavfsizlik sarlavhalari (har ikki domen uchun). .inc — envsubst'dan o'tmaydi, to'g'ridan-to'g'ri include qilinadi.
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;

add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

client_max_body_size 12m;   # rasm yuklash (backend limiti 10 MB)
server_tokens off;
