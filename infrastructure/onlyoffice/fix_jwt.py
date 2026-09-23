import json

path = '/etc/onlyoffice/documentserver/local.json'
cfg = {
    "services": {
        "CoAuthoring": {
            "sql": {
                "type": "postgres",
                "dbHost": "localhost",
                "dbPort": "5432",
                "dbName": "onlyoffice",
                "dbUser": "onlyoffice",
                "dbPass": "onlyoffice"
            },
            "token": {
                "enable": {
                    "request": {
                        "inbox": True,
                        "outbox": True
                    },
                    "browser": True
                },
                "inbox": {
                    "header": "Authorization",
                    "inBody": False
                },
                "outbox": {
                    "header": "Authorization",
                    "inBody": False
                },
                "browser": {
                    "string": "ChangeMeInProductionPleaseUseAtLeast256Bits!"
                }
            },
            "secret": {
                "inbox": {
                    "string": "ChangeMeInProductionPleaseUseAtLeast256Bits!"
                },
                "outbox": {
                    "string": "ChangeMeInProductionPleaseUseAtLeast256Bits!"
                },
                "session": {
                    "string": "ChangeMeInProductionPleaseUseAtLeast256Bits!"
                },
                "browser": {
                    "string": "ChangeMeInProductionPleaseUseAtLeast256Bits!"
                }
            }
        }
    },
    "rabbitmq": {
        "url": "amqp://guest:guest@localhost"
    },
    "wopi": {
        "enable": False,
        "privateKey": ("-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCHoW09XnigZmhQ\n"
            "wMXQh+/cdmkmDoG9TxGkrK0+vCfRN0r/YuGLHAi/GNB5Nv1LH7MKNda/o8H8hNWY\n"
            "vwH4K05oMUERfi0Z+4dPvJ1msYcNzehRxHb/gqwblvRwqvuMPlJdWhjSUY045eUG\n"
            "EN+yMLmJWR4nnr2jASy2JocKWH6e/noJdsOI4D4w9pbOPU71yY2isBjkQ7yYuAUN\n"
            "jxXvsLhgeEe+F8dTgcYouyqupBC664ZBDcqyYuTSHDVb2dBtKWrQxa6HA/QnDsf3\n"
            "ruHloDy/L/juYXB6Z3QOmw7CUvJHOpbeb82P24e4NoQHh1lth6mye9tkWtFiIuvR\n"
            "S/QIIJ1vAgMBAAECggEAIYKAuujcZMTogQsf1KXBXXbkA8MRyvP+J/GB3D4gmFBQ\n"
            "90g28We7wXsgBtLPQgBS+/LRXAfZpcor+9E1a1tHw/ZnXSsPeZvrkofHW9gAxihZ\n"
            "fdpMjFR8sVRakHuuKrg7IVVhTJVZjvU94IHKwvvG22hpSuCtediQc3CRbLzwi9d3\n"
            "u7jO+3stm1jCII73A7z6W2lYfibrkzpYEH7cpaQTh5e4ar/tPH71blwFGBfwlQl8\n"
            "ol+dIjn71n4YbaWIZSPkRVF5QJCBVnbCaPom1SK9YtcCHWMfI/VnPCQ9sA7mV8JL\n"
            "Xi6VQ57edMwCILZr1CdIrgxkemHEN+uAZbUjmuh0AQKBgQC6A6NaWNPRxeUmmOuz\n"
            "+xCWqUlHPPRr+aT/aI1xum8t5LmswzYl6ngsS4XI2oNjWIl8vcf83a3hCVJOwkD+\n"
            "k32/fpy+up5E+UBn3NMc+I1S8keS2gu2HC3TH8GagTMwdo/1BwzGtpT9jGdt6jBq\n"
            "oBM5QHQQ+jxnIg1ubYSJ4Gp+WQKBgQC6qPq0QBPeZuuImTjytx4uPaS7x7LUQWJG\n"
            "O2kmKRovvNTduTtOfpmB3/fbcIGtr2C+9Cd0wiDO6ECO436rOx7fSTcgFRjAxri7\n"
            "rqThBDH88AAZXJmTzjdtjoqgdIef0AYn56wUOJPp/JeT48gQBtQcH7yezCuXYLiF\n"
            "NmkqJ4VRBwKBgHzH0f3aVoWC5hxFOuAqTE900iZKmoAQIIIA5dljwg8cPv3ImftH\n"
            "VUQJiX5aLwcmrlwShyR2pJyv/xm8L5NW52TdD1LWpzMHrQ+/T5NAnLUGt8KoKHEK\n"
            "aCcXR21YvDkHX7xz9Tsb4chQNlXCYqY0KZEfTnzREFHywuXP67f95hJJAoGAKJkE\n"
            "Hhwpth+Qbt9UgYXObKQ/pg/jF0M5Sqk1T3V1Gpjpe2gEPChQ3uyFjhbEPbB9TEry\n"
            "IfTvCdF96RYVwMxVBJ95++JaxeLy3u83MTGmZasVem6ngHxDlfKAuDFgJiQqkpdS\n"
            "1/sOQMANf771DndNvugwMCGcAYqp119kNCTwXBUCgYEAgabS+VpMYr3hr6rctG9s\n"
            "WRZ4Mox7KYOKcdjUKfUHhLEEFCHMGPoMqSN+OI8xSkSQn2s2aZAHeIKDXxPTlTZ7\n"
            "fMZjr/aTe5zl8lMq767G2qEuTiciqkBI6Md3n2rvu5If5tJ6cv7fsml7Mevh9IZe\n"
            "I0xYlyZQmcnPZ4bi6w80G/I=\n"
            "-----END PRIVATE KEY-----\n"),
        "privateKeyOld": ("-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCHoW09XnigZmhQ\n"
            "wMXQh+/cdmkmDoG9TxGkrK0+vCfRN0r/YuGLHAi/GNB5Nv1LH7MKNda/o8H8hNWY\n"
            "vwH4K05oMUERfi0Z+4dPvJ1msYcNzehRxHb/gqwblvRwqvuMPlJdWhjSUY045eUG\n"
            "EN+yMLmJWR4nnr2jASy2JocKWH6e/noJdsOI4D4w9pbOPU71yY2isBjkQ7yYuAUN\n"
            "jxXvsLhgeEe+F8dTgcYouyqupBC664ZBDcqyYuTSHDVb2dBtKWrQxa6HA/QnDsf3\n"
            "ruHloDy/L/juYXB6Z3QOmw7CUvJHOpbeb82P24e4NoQHh1lth6mye9tkWtFiIuvR\n"
            "S/QIIJ1vAgMBAAECggEAIYKAuujcZMTogQsf1KXBXXbkA8MRyvP+J/GB3D4gmFBQ\n"
            "90g28We7wXsgBtLPQgBS+/LRXAfZpcor+9E1a1tHw/ZnXSsPeZvrkofHW9gAxihZ\n"
            "fdpMjFR8sVRakHuuKrg7IVVhTJVZjvU94IHKwvvG22hpSuCtediQc3CRbLzwi9d3\n"
            "u7jO+3stm1jCII73A7z6W2lYfibrkzpYEH7cpaQTh5e4ar/tPH71blwFGBfwlQl8\n"
            "ol+dIjn71n4YbaWIZSPkRVF5QJCBVnbCaPom1SK9YtcCHWMfI/VnPCQ9sA7mV8JL\n"
            "Xi6VQ57edMwCILZr1CdIrgxkemHEN+uAZbUjmuh0AQKBgQC6A6NaWNPRxeUmmOuz\n"
            "+xCWqUlHPPRr+aT/aI1xum8t5LmswzYl6ngsS4XI2oNjWIl8vcf83a3hCVJOwkD+\n"
            "k32/fpy+up5E+UBn3NMc+I1S8keS2gu2HC3TH8GagTMwdo/1BwzGtpT9jGdt6jBq\n"
            "oBM5QHQQ+jxnIg1ubYSJ4Gp+WQKBgQC6qPq0QBPeZuuImTjytx4uPaS7x7LUQWJG\n"
            "O2kmKRovvNTduTtOfpmB3/fbcIGtr2C+9Cd0wiDO6ECO436rOx7fSTcgFRjAxri7\n"
            "rqThBDH88AAZXJmTzjdtjoqgdIef0AYn56wUOJPp/JeT48gQBtQcH7yezCuXYLiF\n"
            "NmkqJ4VRBwKBgHzH0f3aVoWC5hxFOuAqTE900iZKmoAQIIIA5dljwg8cPv3ImftH\n"
            "VUQJiX5aLwcmrlwShyR2pJyv/xm8L5NW52TdD1LWpzMHrQ+/T5NAnLUGt8KoKHEK\n"
            "aCcXR21YvDkHX7xz9Tsb4chQNlXCYqY0KZEfTnzREFHywuXP67f95hJJAoGAKJkE\n"
            "Hhwpth+Qbt9UgYXObKQ/pg/jF0M5Sqk1T3V1Gpjpe2gEPChQ3uyFjhbEPbB9TEry\n"
            "IfTvCdF96RYVwMxVBJ95++JaxeLy3u83MTGmZasVem6ngHxDlfKAuDFgJiQqkpdS\n"
            "1/sOQMANf771DndNvugwMCGcAYqp119kNCTwXBUCgYEAgabS+VpMYr3hr6rctG9s\n"
            "WRZ4Mox7KYOKcdjUKfUHhLEEFCHMGPoMqSN+OI8xSkSQn2s2aZAHeIKDXxPTlTZ7\n"
            "fMZjr/aTe5zl8lMq767G2qEuTiciqkBI6Md3n2rvu5If5tJ6cv7fsml7Mevh9IZe\n"
            "I0xYlyZQmcnPZ4bi6w80G/I=\n"
            "-----END PRIVATE KEY-----\n"),
        "publicKey": ("BgIAAACkAABSU0ExAAgAAAEAAQBvnSAI9EvR6yJi0Vpk23uyqYdtWYcHhDa4"
            "h9uPzW/eljpH8lLCDpsOdGd6cGHu+C+/PKDl4a73xw4n9AOHrsXQailt0NlbNRz"
            "S5GKyyg1Bhuu6EKSuKrsoxoFTxxe+R3hguLDvFY8NBbiYvEPkGLCijcn1Tj3OlvY"
            "wPuCIw3YJev6eflgKhya2LAGjvZ4nHlmJuTCy3xAG5eU4jVHSGFpdUj6M+6pw9JY"
            "brIL/dsRR6M0Nh7FmnbxPh/sZLX4RQTFoTiv4Ab+Y1YT8waO/1jUKsx9L/TZ50Bi"
            "/CByL4WL/SjfRJ7w+raykEU+9gQ4maXbc74fQxcBQaGageF49baGH\n"),
        "publicKeyOld": ("BgIAAACkAABSU0ExAAgAAAEAAQBvnSAI9EvR6yJi0Vpk23uyqYdtWYcHhDa4"
            "h9uPzW/eljpH8lLCDpsOdGd6cGHu+C+/PKDl4a73xw4n9AOHrsXQailt0NlbNRz"
            "S5GKyyg1Bhuu6EKSuKrsoxoFTxxe+R3hguLDvFY8NBbiYvEPkGLCijcn1Tj3OlvY"
            "wPuCIw3YJev6eflgKhya2LAGjvZ4nHlmJuTCy3xAG5eU4jVHSGFpdUj6M+6pw9JY"
            "brIL/dsRR6M0Nh7FmnbxPh/sZLX4RQTFoTiv4Ab+Y1YT8waO/1jUKsx9L/TZ50Bi"
            "/CByL4WL/SjfRJ7w+raykEU+9gQ4maXbc74fQxcBQaGageF49baGH\n"),
        "modulus": ("87A16D3D5E78A0666850C0C5D087EFDC7669260E81BD4F11A4ACAD3EBC27D1374"
            "AFF62E18B1C08BF18D07936FD4B1FB30A35D6BFA3C1FC84D598BF01F82B4E68"
            "3141117E2D19FB874FBC9D66B1870DCDE851C476FF82AC1B96F470AAFB8C3E52"
            "5D5A18D2518D38E5E50610DFB230B989591E279EBDA3012CB626870A587E9EFE"
            "7A0976C388E03E30F696CE3D4EF5C98DA2B018E443BC98B8050D8F15EFB0B86"
            "07847BE17C75381C628BB2AAEA410BAEB86410DCAB262E4D21C355BD9D06D296"
            "AD0C5AE8703F4270EC7F7AEE1E5A03CBF2FF8EE61707A67740E9B0EC252F247"
            "3A96DE6FCD8FDB87B836840787596D87A9B27BDB645AD16222EBD14BF408209D6F\n"),
        "modulusOld": ("87A16D3D5E78A0666850C0C5D087EFDC7669260E81BD4F11A4ACAD3EBC27D1374"
            "AFF62E18B1C08BF18D07936FD4B1FB30A35D6BFA3C1FC84D598BF01F82B4E68"
            "3141117E2D19FB874FBC9D66B1870DCDE851C476FF82AC1B96F470AAFB8C3E52"
            "5D5A18D2518D38E5E50610DFB230B989591E279EBDA3012CB626870A587E9EFE"
            "7A0976C388E03E30F696CE3D4EF5C98DA2B018E443BC98B8050D8F15EFB0B86"
            "07847BE17C75381C628BB2AAEA410BAEB86410DCAB262E4D21C355BD9D06D296"
            "AD0C5AE8703F4270EC7F7AEE1E5A03CBF2FF8EE61707A67740E9B0EC252F247"
            "3A96DE6FCD8FDB87B836840787596D87A9B27BDB645AD16222EBD14BF408209D6F\n"),
        "exponent": 65537,
        "exponentOld": 65537
    },
    "storage": {
        "fs": {
            "secretString": "cubgaw0bW8NANynpOtWc"
        }
    }
}

with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)

print('Done - browser JWT secret added to local.json')
