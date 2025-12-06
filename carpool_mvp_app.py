# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import googlemaps # 用于 Google API 调用
import datetime
import random # 仅作为最终错误回退，但我们现在依赖真实 API

# ----------------------------------------------------------------------
# 核心功能函数
# ----------------------------------------------------------------------

# --- 地理编码函数：将地址转换为坐标 ---
@st.cache_data(ttl=24 * 3600)
def get_coords(address):
    """使用 Google Geocoding API 将地址转换为 (纬度, 经度)"""
    if not address:
        return None
    try:
        api_key = st.secrets["google"]["api_key"]
        gmaps = googlemaps.Client(key=api_key)
        
        geocode_result = gmaps.geocode(address)
        
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            # 返回一个包含 'lat' 和 'lon' 的字典，符合 st.map 的要求
            return {'lat': location['lat'], 'lon': location['lng']}
        return None
    except Exception:
        # 地理编码失败不显示错误，只返回 None
        return None


# --- 路线计算函数：调用 Directions API ---
@st.cache_data(ttl=24 * 3600) # 缓存结果，避免对同一地址重复调用和重复收费
def find_carpool_route(origin, destination, waypoints):
    """
    使用 Google Directions API 计算真实的路线数据。
    """
    if not origin or not destination:
        return None, None, None
    
    try:
        # 从 Streamlit Secrets 中读取安全的 API Key
        api_key = st.secrets["google"]["api_key"]
        gmaps = googlemaps.Client(key=api_key)
        
        # 调用 Directions API
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            optimize_waypoints=True, # 启用 Google 路线优化
            mode="driving"
        )
        
        if not directions_result:
            return None, None, None
            
        # 提取总距离和总时长 (Directions API 返回的是 legs 列表，需要累加)
        total_distance_m = 0
        total_duration_s = 0
        
        for leg in directions_result[0]['legs']:
            total_distance_m += leg['distance']['value']
            total_duration_s += leg['duration']['value']

        # 格式化输出
        total_distance_km = round(total_distance_m / 1000, 1)
        
        # 转换为小时和分钟
        total_duration_h = int(total_duration_s / 3600)
        total_duration_m = int((total_duration_s % 3600) / 60)
        
        total_distance = f"{total_distance_km} 公里"
        total_duration = f"{total_duration_h} 小时 {total_duration_m} 分钟"
        
        # 模拟地图链接
        map_url = "https://maps.google.com/?daddr=" # 简化处理
        
        return total_distance, total_duration, map_url
        
    except Exception as e:
        # 捕捉 API 密钥错误、网络错误或数据解析错误
        # st.error(f"路径计算失败，请检查地址输入或 API 密钥: {e}") # 生产环境中可以注释掉，避免泄露错误细节
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
        origin = st.text_input("📍 司机出发地 (起点)", placeholder="例如：Shenzhen, China")
    
    with col2:
        destination = st.text_input("🏁 最终目的地", placeholder="例如：Guangzhou, China")

    st.subheader("2. 途经点/乘客接送点 (选填)")
    
    waypoints_input = st.text_area("中途接送点 (用逗号分隔)", 
                                   placeholder="例如：Dongguan, China, Huizhou, China")

    # 按钮必须在 form 内部
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
    
    # 计算地图中心点
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
            # 调用核心计算函数
            distance, duration, map_link = find_carpool_route(origin, destination, waypoints_list)
        
        if distance:
            st.success("✅ 路线计算成功！")
            
            # 显示关键数据
            st.metric("总行程距离", distance)
            st.metric("预计总耗时", duration)
            
            # 显示途经点信息
            if waypoints_list:
                st.info(f"包含 {len(waypoints_list)} 个途经点：{', '.join(waypoints_list)}")
            
            st.markdown(f"**[点击查看详细地图路线 (模拟链接)]({map_link})**")
            
            # ----------------------------------------------------------------------
            # 👇 未来费用分摊模型代码将放在这里 👇
            # ----------------------------------------------------------------------

        else:
            # 如果 find_carpool_route 返回 None (API 失败)
            st.error("计算失败，请检查地址输入是否有效，或确认您的 Google Maps API 密钥已正确设置且服务已启用。")