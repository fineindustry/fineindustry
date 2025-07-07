import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json, os, uuid
from collections import Counter

st.set_page_config(page_title="Pipe Cutter Optimizer", layout="wide")
st.title("Pipe Cutting Optimization (First‑Fit‑Decreasing)")
