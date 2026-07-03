// Japan Cities (市区町村) grouped by prefecture code (JIS X 0401)
// Covers major cities and wards — industry-standard for Japanese address forms.
// Source: 政令指定都市・中核市・特例市 + key business areas

export interface CityGroup {
  prefecture: string  // JIS prefecture code (2-digit)
  cities: City[]
}

export interface City {
  code: string       // 5-digit municipality code (JIS X 0402)
  name_ja: string
  name_en: string
}

// Helper maps for quick lookup
const _byPrefecture = new Map<string, City[]>()
const _cityLabelCache = new Map<string, Map<string, string>>()

function _init() {
  for (const group of citiesByPrefecture) {
    _byPrefecture.set(group.prefecture, group.cities)
  }
}

// Cities grouped by prefecture (47都道府県) — major commercial & population centers
export const citiesByPrefecture: CityGroup[] = [
  {
    prefecture: '01', cities: [
      { code: '01100', name_ja: '札幌市', name_en: 'Sapporo' },
      { code: '01202', name_ja: '函館市', name_en: 'Hakodate' },
      { code: '01203', name_ja: '小樽市', name_en: 'Otaru' },
      { code: '01204', name_ja: '旭川市', name_en: 'Asahikawa' },
      { code: '01206', name_ja: '釧路市', name_en: 'Kushiro' },
      { code: '01208', name_ja: '北見市', name_en: 'Kitami' },
      { code: '01213', name_ja: '苫小牧市', name_en: 'Tomakomai' },
      { code: '01101', name_ja: '札幌市中央区', name_en: 'Chuo-ku, Sapporo' },
      { code: '01102', name_ja: '札幌市北区', name_en: 'Kita-ku, Sapporo' },
      { code: '01103', name_ja: '札幌市東区', name_en: 'Higashi-ku, Sapporo' },
      { code: '01104', name_ja: '札幌市白石区', name_en: 'Shiroishi-ku, Sapporo' },
      { code: '01105', name_ja: '札幌市豊平区', name_en: 'Toyohira-ku, Sapporo' },
      { code: '01106', name_ja: '札幌市南区', name_en: 'Minami-ku, Sapporo' },
      { code: '01107', name_ja: '札幌市西区', name_en: 'Nishi-ku, Sapporo' },
      { code: '01108', name_ja: '札幌市厚別区', name_en: 'Atsubetsu-ku, Sapporo' },
      { code: '01109', name_ja: '札幌市手稲区', name_en: 'Teine-ku, Sapporo' },
      { code: '01110', name_ja: '札幌市清田区', name_en: 'Kiyota-ku, Sapporo' },
    ]
  },
  {
    prefecture: '02', cities: [
      { code: '02201', name_ja: '青森市', name_en: 'Aomori' },
      { code: '02203', name_ja: '八戸市', name_en: 'Hachinohe' },
      { code: '02204', name_ja: '弘前市', name_en: 'Hirosaki' },
    ]
  },
  {
    prefecture: '03', cities: [
      { code: '03201', name_ja: '盛岡市', name_en: 'Morioka' },
    ]
  },
  {
    prefecture: '04', cities: [
      { code: '04100', name_ja: '仙台市', name_en: 'Sendai' },
      { code: '04101', name_ja: '仙台市青葉区', name_en: 'Aoba-ku, Sendai' },
      { code: '04102', name_ja: '仙台市宮城野区', name_en: 'Miyagino-ku, Sendai' },
      { code: '04103', name_ja: '仙台市若林区', name_en: 'Wakabayashi-ku, Sendai' },
      { code: '04104', name_ja: '仙台市太白区', name_en: 'Taihaku-ku, Sendai' },
      { code: '04105', name_ja: '仙台市泉区', name_en: 'Izumi-ku, Sendai' },
    ]
  },
  {
    prefecture: '05', cities: [
      { code: '05201', name_ja: '秋田市', name_en: 'Akita' },
    ]
  },
  {
    prefecture: '06', cities: [
      { code: '06201', name_ja: '山形市', name_en: 'Yamagata' },
    ]
  },
  {
    prefecture: '07', cities: [
      { code: '07201', name_ja: '福島市', name_en: 'Fukushima' },
      { code: '07203', name_ja: '郡山市', name_en: 'Koriyama' },
      { code: '07204', name_ja: 'いわき市', name_en: 'Iwaki' },
    ]
  },
  {
    prefecture: '08', cities: [
      { code: '08201', name_ja: '水戸市', name_en: 'Mito' },
      { code: '08220', name_ja: 'つくば市', name_en: 'Tsukuba' },
    ]
  },
  {
    prefecture: '09', cities: [
      { code: '09201', name_ja: '宇都宮市', name_en: 'Utsunomiya' },
    ]
  },
  {
    prefecture: '10', cities: [
      { code: '10201', name_ja: '前橋市', name_en: 'Maebashi' },
      { code: '10202', name_ja: '高崎市', name_en: 'Takasaki' },
    ]
  },
  {
    prefecture: '11', cities: [
      { code: '11100', name_ja: 'さいたま市', name_en: 'Saitama' },
      { code: '11101', name_ja: 'さいたま市西区', name_en: 'Nishi-ku, Saitama' },
      { code: '11102', name_ja: 'さいたま市北区', name_en: 'Kita-ku, Saitama' },
      { code: '11103', name_ja: 'さいたま市大宮区', name_en: 'Omiya-ku, Saitama' },
      { code: '11104', name_ja: 'さいたま市見沼区', name_en: 'Minuma-ku, Saitama' },
      { code: '11105', name_ja: 'さいたま市中央区', name_en: 'Chuo-ku, Saitama' },
      { code: '11106', name_ja: 'さいたま市桜区', name_en: 'Sakura-ku, Saitama' },
      { code: '11107', name_ja: 'さいたま市浦和区', name_en: 'Urawa-ku, Saitama' },
      { code: '11108', name_ja: 'さいたま市南区', name_en: 'Minami-ku, Saitama' },
      { code: '11109', name_ja: 'さいたま市緑区', name_en: 'Midori-ku, Saitama' },
      { code: '11110', name_ja: 'さいたま市岩槻区', name_en: 'Iwatsuki-ku, Saitama' },
      { code: '11201', name_ja: '川越市', name_en: 'Kawagoe' },
      { code: '11203', name_ja: '川口市', name_en: 'Kawaguchi' },
      { code: '11222', name_ja: '越谷市', name_en: 'Koshigaya' },
      { code: '11229', name_ja: '所沢市', name_en: 'Tokorozawa' },
    ]
  },
  {
    prefecture: '12', cities: [
      { code: '12100', name_ja: '千葉市', name_en: 'Chiba' },
      { code: '12101', name_ja: '千葉市中央区', name_en: 'Chuo-ku, Chiba' },
      { code: '12102', name_ja: '千葉市花見川区', name_en: 'Hanamigawa-ku, Chiba' },
      { code: '12103', name_ja: '千葉市稲毛区', name_en: 'Inage-ku, Chiba' },
      { code: '12104', name_ja: '千葉市若葉区', name_en: 'Wakaba-ku, Chiba' },
      { code: '12105', name_ja: '千葉市緑区', name_en: 'Midori-ku, Chiba' },
      { code: '12106', name_ja: '千葉市美浜区', name_en: 'Mihama-ku, Chiba' },
      { code: '12203', name_ja: '市川市', name_en: 'Ichikawa' },
      { code: '12204', name_ja: '船橋市', name_en: 'Funabashi' },
      { code: '12207', name_ja: '松戸市', name_en: 'Matsudo' },
      { code: '12217', name_ja: '柏市', name_en: 'Kashiwa' },
      { code: '12227', name_ja: '浦安市', name_en: 'Urayasu' },
    ]
  },
  {
    prefecture: '13', cities: [
      { code: '13101', name_ja: '千代田区', name_en: 'Chiyoda-ku' },
      { code: '13102', name_ja: '中央区', name_en: 'Chuo-ku' },
      { code: '13103', name_ja: '港区', name_en: 'Minato-ku' },
      { code: '13104', name_ja: '新宿区', name_en: 'Shinjuku-ku' },
      { code: '13105', name_ja: '文京区', name_en: 'Bunkyo-ku' },
      { code: '13106', name_ja: '台東区', name_en: 'Taito-ku' },
      { code: '13107', name_ja: '墨田区', name_en: 'Sumida-ku' },
      { code: '13108', name_ja: '江東区', name_en: 'Koto-ku' },
      { code: '13109', name_ja: '品川区', name_en: 'Shinagawa-ku' },
      { code: '13110', name_ja: '目黒区', name_en: 'Meguro-ku' },
      { code: '13111', name_ja: '大田区', name_en: 'Ota-ku' },
      { code: '13112', name_ja: '世田谷区', name_en: 'Setagaya-ku' },
      { code: '13113', name_ja: '渋谷区', name_en: 'Shibuya-ku' },
      { code: '13114', name_ja: '中野区', name_en: 'Nakano-ku' },
      { code: '13115', name_ja: '杉並区', name_en: 'Suginami-ku' },
      { code: '13116', name_ja: '豊島区', name_en: 'Toshima-ku' },
      { code: '13117', name_ja: '北区', name_en: 'Kita-ku' },
      { code: '13118', name_ja: '荒川区', name_en: 'Arakawa-ku' },
      { code: '13119', name_ja: '板橋区', name_en: 'Itabashi-ku' },
      { code: '13120', name_ja: '練馬区', name_en: 'Nerima-ku' },
      { code: '13121', name_ja: '足立区', name_en: 'Adachi-ku' },
      { code: '13122', name_ja: '葛飾区', name_en: 'Katsushika-ku' },
      { code: '13123', name_ja: '江戸川区', name_en: 'Edogawa-ku' },
      { code: '13201', name_ja: '八王子市', name_en: 'Hachioji' },
      { code: '13202', name_ja: '立川市', name_en: 'Tachikawa' },
      { code: '13204', name_ja: '三鷹市', name_en: 'Mitaka' },
      { code: '13206', name_ja: '府中市', name_en: 'Fuchu' },
      { code: '13208', name_ja: '調布市', name_en: 'Chofu' },
      { code: '13209', name_ja: '町田市', name_en: 'Machida' },
      { code: '13214', name_ja: '国分寺市', name_en: 'Kokubunji' },
      { code: '13229', name_ja: '西東京市', name_en: 'Nishitokyo' },
    ]
  },
  {
    prefecture: '14', cities: [
      { code: '14100', name_ja: '横浜市', name_en: 'Yokohama' },
      { code: '14101', name_ja: '横浜市鶴見区', name_en: 'Tsurumi-ku, Yokohama' },
      { code: '14102', name_ja: '横浜市神奈川区', name_en: 'Kanagawa-ku, Yokohama' },
      { code: '14103', name_ja: '横浜市西区', name_en: 'Nishi-ku, Yokohama' },
      { code: '14104', name_ja: '横浜市中区', name_en: 'Naka-ku, Yokohama' },
      { code: '14105', name_ja: '横浜市南区', name_en: 'Minami-ku, Yokohama' },
      { code: '14106', name_ja: '横浜市保土ケ谷区', name_en: 'Hodogaya-ku, Yokohama' },
      { code: '14107', name_ja: '横浜市磯子区', name_en: 'Isogo-ku, Yokohama' },
      { code: '14108', name_ja: '横浜市金沢区', name_en: 'Kanazawa-ku, Yokohama' },
      { code: '14109', name_ja: '横浜市港北区', name_en: 'Kohoku-ku, Yokohama' },
      { code: '14110', name_ja: '横浜市戸塚区', name_en: 'Totsuka-ku, Yokohama' },
      { code: '14111', name_ja: '横浜市港南区', name_en: 'Konan-ku, Yokohama' },
      { code: '14112', name_ja: '横浜市旭区', name_en: 'Asahi-ku, Yokohama' },
      { code: '14113', name_ja: '横浜市緑区', name_en: 'Midori-ku, Yokohama' },
      { code: '14114', name_ja: '横浜市瀬谷区', name_en: 'Seya-ku, Yokohama' },
      { code: '14115', name_ja: '横浜市栄区', name_en: 'Sakae-ku, Yokohama' },
      { code: '14116', name_ja: '横浜市泉区', name_en: 'Izumi-ku, Yokohama' },
      { code: '14117', name_ja: '横浜市青葉区', name_en: 'Aoba-ku, Yokohama' },
      { code: '14118', name_ja: '横浜市都筑区', name_en: 'Tsuzuki-ku, Yokohama' },
      { code: '14130', name_ja: '川崎市', name_en: 'Kawasaki' },
      { code: '14131', name_ja: '川崎市川崎区', name_en: 'Kawasaki-ku, Kawasaki' },
      { code: '14132', name_ja: '川崎市幸区', name_en: 'Saiwai-ku, Kawasaki' },
      { code: '14133', name_ja: '川崎市中原区', name_en: 'Nakahara-ku, Kawasaki' },
      { code: '14134', name_ja: '川崎市高津区', name_en: 'Takatsu-ku, Kawasaki' },
      { code: '14135', name_ja: '川崎市多摩区', name_en: 'Tama-ku, Kawasaki' },
      { code: '14136', name_ja: '川崎市宮前区', name_en: 'Miyamae-ku, Kawasaki' },
      { code: '14137', name_ja: '川崎市麻生区', name_en: 'Asao-ku, Kawasaki' },
      { code: '14150', name_ja: '相模原市', name_en: 'Sagamihara' },
      { code: '14205', name_ja: '藤沢市', name_en: 'Fujisawa' },
      { code: '14206', name_ja: '小田原市', name_en: 'Odawara' },
      { code: '14218', name_ja: '鎌倉市', name_en: 'Kamakura' },
      { code: '14201', name_ja: '横須賀市', name_en: 'Yokosuka' },
    ]
  },
  {
    prefecture: '15', cities: [
      { code: '15100', name_ja: '新潟市', name_en: 'Niigata' },
    ]
  },
  {
    prefecture: '16', cities: [
      { code: '16201', name_ja: '富山市', name_en: 'Toyama' },
    ]
  },
  {
    prefecture: '17', cities: [
      { code: '17201', name_ja: '金沢市', name_en: 'Kanazawa' },
    ]
  },
  {
    prefecture: '18', cities: [
      { code: '18201', name_ja: '福井市', name_en: 'Fukui' },
    ]
  },
  {
    prefecture: '19', cities: [
      { code: '19201', name_ja: '甲府市', name_en: 'Kofu' },
    ]
  },
  {
    prefecture: '20', cities: [
      { code: '20201', name_ja: '長野市', name_en: 'Nagano' },
      { code: '20202', name_ja: '松本市', name_en: 'Matsumoto' },
    ]
  },
  {
    prefecture: '21', cities: [
      { code: '21201', name_ja: '岐阜市', name_en: 'Gifu' },
    ]
  },
  {
    prefecture: '22', cities: [
      { code: '22100', name_ja: '静岡市', name_en: 'Shizuoka' },
      { code: '22130', name_ja: '浜松市', name_en: 'Hamamatsu' },
    ]
  },
  {
    prefecture: '23', cities: [
      { code: '23100', name_ja: '名古屋市', name_en: 'Nagoya' },
      { code: '23101', name_ja: '名古屋市千種区', name_en: 'Chikusa-ku, Nagoya' },
      { code: '23102', name_ja: '名古屋市東区', name_en: 'Higashi-ku, Nagoya' },
      { code: '23103', name_ja: '名古屋市北区', name_en: 'Kita-ku, Nagoya' },
      { code: '23104', name_ja: '名古屋市西区', name_en: 'Nishi-ku, Nagoya' },
      { code: '23105', name_ja: '名古屋市中村区', name_en: 'Nakamura-ku, Nagoya' },
      { code: '23106', name_ja: '名古屋市中区', name_en: 'Naka-ku, Nagoya' },
      { code: '23107', name_ja: '名古屋市昭和区', name_en: 'Showa-ku, Nagoya' },
      { code: '23108', name_ja: '名古屋市瑞穂区', name_en: 'Mizuho-ku, Nagoya' },
      { code: '23109', name_ja: '名古屋市熱田区', name_en: 'Atsuta-ku, Nagoya' },
      { code: '23110', name_ja: '名古屋市中川区', name_en: 'Nakagawa-ku, Nagoya' },
      { code: '23111', name_ja: '名古屋市港区', name_en: 'Minato-ku, Nagoya' },
      { code: '23112', name_ja: '名古屋市南区', name_en: 'Minami-ku, Nagoya' },
      { code: '23113', name_ja: '名古屋市守山区', name_en: 'Moriyama-ku, Nagoya' },
      { code: '23114', name_ja: '名古屋市緑区', name_en: 'Midori-ku, Nagoya' },
      { code: '23115', name_ja: '名古屋市名東区', name_en: 'Meito-ku, Nagoya' },
      { code: '23116', name_ja: '名古屋市天白区', name_en: 'Tempaku-ku, Nagoya' },
      { code: '23202', name_ja: '豊橋市', name_en: 'Toyohashi' },
      { code: '23203', name_ja: '岡崎市', name_en: 'Okazaki' },
      { code: '23211', name_ja: '豊田市', name_en: 'Toyota' },
    ]
  },
  {
    prefecture: '24', cities: [
      { code: '24201', name_ja: '津市', name_en: 'Tsu' },
      { code: '24202', name_ja: '四日市市', name_en: 'Yokkaichi' },
    ]
  },
  {
    prefecture: '25', cities: [
      { code: '25201', name_ja: '大津市', name_en: 'Otsu' },
    ]
  },
  {
    prefecture: '26', cities: [
      { code: '26100', name_ja: '京都市', name_en: 'Kyoto' },
      { code: '26101', name_ja: '京都市北区', name_en: 'Kita-ku, Kyoto' },
      { code: '26102', name_ja: '京都市上京区', name_en: 'Kamigyo-ku, Kyoto' },
      { code: '26103', name_ja: '京都市左京区', name_en: 'Sakyo-ku, Kyoto' },
      { code: '26104', name_ja: '京都市中京区', name_en: 'Nakagyo-ku, Kyoto' },
      { code: '26105', name_ja: '京都市東山区', name_en: 'Higashiyama-ku, Kyoto' },
      { code: '26106', name_ja: '京都市下京区', name_en: 'Shimogyo-ku, Kyoto' },
      { code: '26107', name_ja: '京都市南区', name_en: 'Minami-ku, Kyoto' },
      { code: '26108', name_ja: '京都市右京区', name_en: 'Ukyo-ku, Kyoto' },
      { code: '26109', name_ja: '京都市伏見区', name_en: 'Fushimi-ku, Kyoto' },
      { code: '26110', name_ja: '京都市山科区', name_en: 'Yamashina-ku, Kyoto' },
      { code: '26111', name_ja: '京都市西京区', name_en: 'Nishikyo-ku, Kyoto' },
    ]
  },
  {
    prefecture: '27', cities: [
      { code: '27100', name_ja: '大阪市', name_en: 'Osaka' },
      { code: '27102', name_ja: '大阪市都島区', name_en: 'Miyakojima-ku, Osaka' },
      { code: '27103', name_ja: '大阪市福島区', name_en: 'Fukushima-ku, Osaka' },
      { code: '27104', name_ja: '大阪市此花区', name_en: 'Konohana-ku, Osaka' },
      { code: '27106', name_ja: '大阪市西区', name_en: 'Nishi-ku, Osaka' },
      { code: '27107', name_ja: '大阪市港区', name_en: 'Minato-ku, Osaka' },
      { code: '27108', name_ja: '大阪市大正区', name_en: 'Taisho-ku, Osaka' },
      { code: '27109', name_ja: '大阪市天王寺区', name_en: 'Tennoji-ku, Osaka' },
      { code: '27111', name_ja: '大阪市浪速区', name_en: 'Naniwa-ku, Osaka' },
      { code: '27113', name_ja: '大阪市西淀川区', name_en: 'Nishiyodogawa-ku, Osaka' },
      { code: '27114', name_ja: '大阪市東淀川区', name_en: 'Higashiyodogawa-ku, Osaka' },
      { code: '27115', name_ja: '大阪市東成区', name_en: 'Higashinari-ku, Osaka' },
      { code: '27116', name_ja: '大阪市生野区', name_en: 'Ikuno-ku, Osaka' },
      { code: '27117', name_ja: '大阪市旭区', name_en: 'Asahi-ku, Osaka' },
      { code: '27118', name_ja: '大阪市城東区', name_en: 'Joto-ku, Osaka' },
      { code: '27119', name_ja: '大阪市阿倍野区', name_en: 'Abeno-ku, Osaka' },
      { code: '27120', name_ja: '大阪市住吉区', name_en: 'Sumiyoshi-ku, Osaka' },
      { code: '27121', name_ja: '大阪市東住吉区', name_en: 'Higashisumiyoshi-ku, Osaka' },
      { code: '27122', name_ja: '大阪市西成区', name_en: 'Nishinari-ku, Osaka' },
      { code: '27123', name_ja: '大阪市淀川区', name_en: 'Yodogawa-ku, Osaka' },
      { code: '27124', name_ja: '大阪市鶴見区', name_en: 'Tsurumi-ku, Osaka' },
      { code: '27125', name_ja: '大阪市住之江区', name_en: 'Suminoe-ku, Osaka' },
      { code: '27126', name_ja: '大阪市平野区', name_en: 'Hirano-ku, Osaka' },
      { code: '27127', name_ja: '大阪市北区', name_en: 'Kita-ku, Osaka' },
      { code: '27128', name_ja: '大阪市中央区', name_en: 'Chuo-ku, Osaka' },
      { code: '27140', name_ja: '堺市', name_en: 'Sakai' },
      { code: '27202', name_ja: '岸和田市', name_en: 'Kishiwada' },
      { code: '27207', name_ja: '吹田市', name_en: 'Suita' },
      { code: '27210', name_ja: '枚方市', name_en: 'Hirakata' },
      { code: '27212', name_ja: '八尾市', name_en: 'Yao' },
      { code: '27220', name_ja: '箕面市', name_en: 'Minoh' },
      { code: '27227', name_ja: '東大阪市', name_en: 'Higashiosaka' },
    ]
  },
  {
    prefecture: '28', cities: [
      { code: '28100', name_ja: '神戸市', name_en: 'Kobe' },
      { code: '28101', name_ja: '神戸市東灘区', name_en: 'Higashinada-ku, Kobe' },
      { code: '28102', name_ja: '神戸市灘区', name_en: 'Nada-ku, Kobe' },
      { code: '28105', name_ja: '神戸市兵庫区', name_en: 'Hyogo-ku, Kobe' },
      { code: '28106', name_ja: '神戸市長田区', name_en: 'Nagata-ku, Kobe' },
      { code: '28107', name_ja: '神戸市須磨区', name_en: 'Suma-ku, Kobe' },
      { code: '28108', name_ja: '神戸市垂水区', name_en: 'Tarumi-ku, Kobe' },
      { code: '28109', name_ja: '神戸市北区', name_en: 'Kita-ku, Kobe' },
      { code: '28110', name_ja: '神戸市中央区', name_en: 'Chuo-ku, Kobe' },
      { code: '28111', name_ja: '神戸市西区', name_en: 'Nishi-ku, Kobe' },
      { code: '28202', name_ja: '尼崎市', name_en: 'Amagasaki' },
      { code: '28204', name_ja: '西宮市', name_en: 'Nishinomiya' },
      { code: '28207', name_ja: '伊丹市', name_en: 'Itami' },
      { code: '28214', name_ja: '宝塚市', name_en: 'Takarazuka' },
      { code: '28220', name_ja: '加古川市', name_en: 'Kakogawa' },
      { code: '28224', name_ja: '姫路市', name_en: 'Himeji' },
    ]
  },
  {
    prefecture: '29', cities: [
      { code: '29201', name_ja: '奈良市', name_en: 'Nara' },
    ]
  },
  {
    prefecture: '30', cities: [
      { code: '30201', name_ja: '和歌山市', name_en: 'Wakayama' },
    ]
  },
  {
    prefecture: '31', cities: [
      { code: '31201', name_ja: '鳥取市', name_en: 'Tottori' },
    ]
  },
  {
    prefecture: '32', cities: [
      { code: '32201', name_ja: '松江市', name_en: 'Matsue' },
    ]
  },
  {
    prefecture: '33', cities: [
      { code: '33100', name_ja: '岡山市', name_en: 'Okayama' },
      { code: '33202', name_ja: '倉敷市', name_en: 'Kurashiki' },
    ]
  },
  {
    prefecture: '34', cities: [
      { code: '34100', name_ja: '広島市', name_en: 'Hiroshima' },
      { code: '34101', name_ja: '広島市中区', name_en: 'Naka-ku, Hiroshima' },
      { code: '34102', name_ja: '広島市東区', name_en: 'Higashi-ku, Hiroshima' },
      { code: '34103', name_ja: '広島市南区', name_en: 'Minami-ku, Hiroshima' },
      { code: '34104', name_ja: '広島市西区', name_en: 'Nishi-ku, Hiroshima' },
      { code: '34105', name_ja: '広島市安佐南区', name_en: 'Asaminami-ku, Hiroshima' },
      { code: '34106', name_ja: '広島市安佐北区', name_en: 'Asakita-ku, Hiroshima' },
      { code: '34107', name_ja: '広島市安芸区', name_en: 'Aki-ku, Hiroshima' },
      { code: '34108', name_ja: '広島市佐伯区', name_en: 'Saeki-ku, Hiroshima' },
      { code: '34207', name_ja: '福山市', name_en: 'Fukuyama' },
    ]
  },
  {
    prefecture: '35', cities: [
      { code: '35201', name_ja: '下関市', name_en: 'Shimonoseki' },
    ]
  },
  {
    prefecture: '36', cities: [
      { code: '36201', name_ja: '徳島市', name_en: 'Tokushima' },
    ]
  },
  {
    prefecture: '37', cities: [
      { code: '37201', name_ja: '高松市', name_en: 'Takamatsu' },
    ]
  },
  {
    prefecture: '38', cities: [
      { code: '38201', name_ja: '松山市', name_en: 'Matsuyama' },
    ]
  },
  {
    prefecture: '39', cities: [
      { code: '39201', name_ja: '高知市', name_en: 'Kochi' },
    ]
  },
  {
    prefecture: '40', cities: [
      { code: '40100', name_ja: '福岡市', name_en: 'Fukuoka' },
      { code: '40101', name_ja: '福岡市東区', name_en: 'Higashi-ku, Fukuoka' },
      { code: '40102', name_ja: '福岡市博多区', name_en: 'Hakata-ku, Fukuoka' },
      { code: '40103', name_ja: '福岡市中央区', name_en: 'Chuo-ku, Fukuoka' },
      { code: '40104', name_ja: '福岡市南区', name_en: 'Minami-ku, Fukuoka' },
      { code: '40105', name_ja: '福岡市西区', name_en: 'Nishi-ku, Fukuoka' },
      { code: '40106', name_ja: '福岡市城南区', name_en: 'Jonan-ku, Fukuoka' },
      { code: '40107', name_ja: '福岡市早良区', name_en: 'Sawara-ku, Fukuoka' },
      { code: '40130', name_ja: '北九州市', name_en: 'Kitakyushu' },
      { code: '40203', name_ja: '久留米市', name_en: 'Kurume' },
    ]
  },
  {
    prefecture: '41', cities: [
      { code: '41201', name_ja: '佐賀市', name_en: 'Saga' },
    ]
  },
  {
    prefecture: '42', cities: [
      { code: '42201', name_ja: '長崎市', name_en: 'Nagasaki' },
    ]
  },
  {
    prefecture: '43', cities: [
      { code: '43100', name_ja: '熊本市', name_en: 'Kumamoto' },
    ]
  },
  {
    prefecture: '44', cities: [
      { code: '44201', name_ja: '大分市', name_en: 'Oita' },
    ]
  },
  {
    prefecture: '45', cities: [
      { code: '45201', name_ja: '宮崎市', name_en: 'Miyazaki' },
    ]
  },
  {
    prefecture: '46', cities: [
      { code: '46201', name_ja: '鹿児島市', name_en: 'Kagoshima' },
    ]
  },
  {
    prefecture: '47', cities: [
      { code: '47201', name_ja: '那覇市', name_en: 'Naha' },
    ]
  },
]

// Initialize the lookup map
_init()

export function getCitiesByPrefecture(prefectureCode: string): City[] {
  return _byPrefecture.get(prefectureCode) || []
}

export function cityLabel(city: City, locale: string = 'ja'): string {
  if (locale === 'ja') return city.name_ja
  return `${city.name_ja} (${city.name_en})`
}

export function getAllCities(): City[] {
  return citiesByPrefecture.flatMap(g => g.cities)
}
