# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests # <-- 替换了 googlemaps
import datetime

# ----------------------------------------------------------------------
# 核心功能函数 (现在使用 requests 直接调用 Google API)
# ----------------------------------------------------------------------

# --- 地理编码函数：将地址转换为坐标 (使用 requests) ---
@st.cache_data(ttl=24 * 3600)
def get_coords(address):
    """使用 Google Geocoding API 将地址转换为 (纬度, 经度)"""
    if not address:
        return None
    try:
        api_key = st.secrets["google"]["api_key"]
        
        # 构建 Geocoding API 请求
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": api_key
        }
        
        response = requests.get(geocode_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "OK" and data["results"]:
            location = data["results"][0]['geometry']['location']
            return {'lat': location['lat'], 'lon': location['lng']}
        return None
    except Exception:
        return None

# --- 地址候选项函数：使用 Geocoding 模糊搜索 ---
@st.cache_data(ttl=24 * 3600)
def get_address_options(partial_address):
    """
    接收部分地址，返回一个包含最多5个精确地址字符串的列表。
    """
    if not partial_address or len(partial_address) < 3:
        return []
        
    try:
        api_key = st.secrets["google"]["api_key"]
        
        # 构造 Geocoding API 请求
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": partial_address,
            "key": api_key,
            "bounds": "30,-120|50,-70" # 限制在美国东北部区域 (可选，提高精确度)
        }
        
        response = requests.get(geocode_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        options = []
        if data.get("status") == "OK" and data["results"]:
            # 提取前5个结果作为候选项
            for result in data["results"][:5]:
                options.append(result['formatted_address'])
        return options
    except Exception:
        return []

# --- 路线计算函数：调用 Directions API (使用 requests) ---
@st.cache_data(ttl=24 * 3600)
def find_carpool_route(origin, destination, waypoints):
    """
    使用 Google Directions API 计算真实的路线数据。
    """
    if not origin or not destination:
        return None, None, None
    
    try:
        api_key = st.secrets["google"]["api_key"]
        
        # 1. 构造 Directions API 请求
        directions_url = "https://maps.googleapis.com/maps/api/directions/json"
        
        # 准备途经点字符串
        waypoints_str = "|".join(waypoints) if waypoints else ""
        
        params = {
            "origin": origin,
            "destination": destination,
            "waypoints": "optimize:true|" + waypoints_str if waypoints_str else "",
            "mode": "driving",
            "key": api_key
        }
        
        # 2. 发送请求
        response = requests.get(directions_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "OK" or not data["routes"]:
            return None, None, None
            
        # 3. 解析结果 (累加所有路段的距离和时长)
        total_distance_m = 0
        total_duration_s = 0
        
        for leg in data["routes"][0]['legs']:
            total_distance_m += leg['distance']['value']
            total_duration_s += leg['duration']['value']

        # 格式化输出
        total_distance_km = round(total_distance_m / 1000, 1)
        total_duration_h = int(total_duration_s / 3600)
        total_duration_m = int((total_duration_s % 3600) / 60)
        
        total_distance = f"{total_distance_km} 公里"
        total_duration = f"{total_duration_h} 小时 {total_duration_m} 分钟"
        map_url = "https://maps.google.com/?q=" + destination
        
        return total_distance, total_duration, map_url
        
    except Exception:
        # 捕获 API 密钥错误、网络错误或数据解析错误
        return None, None, None
# ----------------------------------------------------------------------


# --- Streamlit 界面 ---

st.set_page_config(page_title="简易拼车行程计算器", layout="wide")

st.title("🚗 城际拼车行程计算器 (MVP)")
st.markdown("---")


# 使用 form 结构收集数据，统一提交
with st.form("carpool_form"):
    st.header("1. 行程路线输入") 
    
    col1, col2 = st.columns(2)
    
    with col1:
        origin = st.text_input("📍 司机出发地 (起点)", placeholder="例如：New York, NY")
    
    with col2:
        destination = st.text_input("🏁 最终目的地", placeholder="例如：Boston, MA")

    st.subheader("2. 途经点/乘客接送点 (选填)")
    
    waypoints_input = st.text_area("中途接送点 (用逗号分隔)", 
                                   placeholder="例如：Stamford, CT, Providence, RI")

    submitted = st.form_submit_button("📐 计算最佳路线")

# ----------------------------------------------------------------------
# 实时地图可视化 (在表单之后)
# ----------------------------------------------------------------------

# 1. 获取起点和终点的坐标
origin_coords = get_coords(origin)
destination_coords = get_coords(destination)

# 2. 准备地图数据帧
map_data = []

if origin_coords:
    map_data.append({'lat': origin_coords['lat'], 'lon': origin_coords['lon'], 'name': '起点'})

if destination_coords:
    map_data.append({'lat': destination_coords['lat'], 'lon': destination_coords['lon'], 'name': '终点'})

# 3. 显示地图
if map_data:
    df = pd.DataFrame(map_data)
    
    st.subheader("📍 实时路线可视化")
    
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()
    
    st.map(df, 
           latitude=center_lat,
           longitude=center_lon,
           zoom=6) 
else:
    st.info("请输入起点和终点，地图将自动显示位置。")


# ----------------------------------------------------------------------
# 计算结果展示 (点击提交后)
# ----------------------------------------------------------------------

if submitted:
    if not origin or not destination:
        st.error("请输入完整的起点和终点！")
    else:
        # 清理途经点输入
        waypoints_list = [w.strip() for w in waypoints_input.split(',') if w.strip()]
        
        st.subheader("--- 计算结果 ---")
        
        with st.spinner("正在调用 Google 路径优化算法..."):
            distance, duration, map_link = find_carpool_route(origin, destination, waypoints_list)
        
        if distance:
            st.success("✅ 路线计算成功！")
            
            # 显示关键数据
            st.metric("总行程距离", distance)
            st.metric("预计总耗时", duration)
            
            # 显示途经点信息
            if waypoints_list:
                st.info(f"包含 {len(waypoints_list)} 个途经点：{', '.join(waypoints_list)}")
            
            st.markdown(f"**[点击查看详细地图路线 (Google Maps)]({map_link})**")
            
            # ----------------------------------------------------------------------
            # 👇 未来费用分摊模型代码将放在这里 👇
            # ----------------------------------------------------------------------

        else:
            # 如果 find_carpool_route 返回 None (API 失败)
            st.error("计算失败，请检查地址输入是否有效，或确认您的 Google Maps API 密钥已正确设置且服务已启用。")