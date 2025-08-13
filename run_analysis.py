5#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Analysis Excel Generator - 통합 실행 파일
이미지 분석 결과를 Excel 파일로 생성하는 통합 도구
"""

import sys
import os
import locale
import subprocess

# 한글 자소 분리 문제 해결을 위한 인코딩 설정
if sys.platform.startswith('darwin'):  # macOS
    os.environ['LC_ALL'] = 'en_US.UTF-8'
    os.environ['LANG'] = 'en_US.UTF-8'
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except:
        pass

def print_banner():
    """프로그램 시작 배너 출력"""
    print("=" * 70)
    print("🔬 Image Analysis Excel Generator")
    print("   이미지 분석 결과 Excel 파일 생성 도구")
    print("=" * 70)
    print()

def print_menu():
    """메뉴 출력"""
    print("📋 사용 가능한 기능:")
    print()
    print("1. 기본 이미지-결과 매칭 Excel 생성")
    print("   └── 이미지 쌍 + 추론 결과 (30개 샘플)")
    print("   └── 출력: image_analysis_results.xlsx")
    print()
    print("2. 필터링 최적화 Excel 생성")
    print("   └── 이미지 쌍 + 추론 결과 (셀 기반 이미지)")
    print("   └── 출력: image_pairs_with_filter.xlsx")
    print()
    print("3. 완전 통합 Excel 생성 (권장)")
    print("   └── 이미지 쌍 + 추론 결과 + DMT 분석 결과")
    print("   └── 모든 데이터 처리 (7,917개 파일)")
    print("   └── 출력: merged_analysis_results.xlsx")
    print()
    print("4. 의존성 설치")
    print("   └── 필요한 Python 패키지 설치")
    print()
    print("5. 가상환경 설정")
    print("   └── Python 가상환경 생성 및 활성화")
    print()
    print("0. 종료")
    print()

def check_dependencies():
    """필요한 패키지가 설치되어 있는지 확인"""
    required_packages = ['openpyxl', 'pillow']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'pillow':
                import PIL
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    return missing_packages

def install_dependencies():
    """필요한 패키지 설치"""
    print("📦 Python 패키지 설치 중...")
    print()
    
    packages = ['openpyxl', 'pillow']
    
    for package in packages:
        print(f"설치 중: {package}")
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {package} 설치 완료")
            else:
                print(f"❌ {package} 설치 실패: {result.stderr}")
        except Exception as e:
            print(f"❌ {package} 설치 중 오류: {e}")
        print()
    
    print("패키지 설치 완료!")

def setup_venv():
    """가상환경 설정"""
    print("🐍 Python 가상환경 설정 중...")
    print()
    
    venv_path = "venv"
    
    if not os.path.exists(venv_path):
        print("가상환경 생성 중...")
        try:
            result = subprocess.run([sys.executable, '-m', 'venv', venv_path], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 가상환경 생성 완료")
            else:
                print(f"❌ 가상환경 생성 실패: {result.stderr}")
                return
        except Exception as e:
            print(f"❌ 가상환경 생성 중 오류: {e}")
            return
    else:
        print("✅ 가상환경이 이미 존재합니다")
    
    print()
    print("가상환경 활성화 방법:")
    if sys.platform.startswith('win'):
        print(f"  {venv_path}\\Scripts\\activate")
    else:
        print(f"  source {venv_path}/bin/activate")
    print()

def run_script(script_name, description):
    """스크립트 실행"""
    print(f"🚀 {description}")
    print(f"실행 중: {script_name}")
    print("=" * 50)
    print()
    
    try:
        # 현재 디렉토리에서 스크립트 실행
        result = subprocess.run([sys.executable, script_name], 
                              cwd=os.getcwd(),
                              text=True)
        
        if result.returncode == 0:
            print()
            print("=" * 50)
            print(f"✅ {description} 완료!")
        else:
            print()
            print("=" * 50)
            print(f"❌ {description} 중 오류가 발생했습니다.")
            
    except FileNotFoundError:
        print(f"❌ 스크립트 파일을 찾을 수 없습니다: {script_name}")
        print("현재 디렉토리에 해당 파일이 있는지 확인해주세요.")
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")

def main():
    """메인 함수"""
    print_banner()
    
    while True:
        print_menu()
        
        try:
            choice = input("선택하세요 (0-5): ").strip()
            print()
            
            if choice == '0':
                print("👋 프로그램을 종료합니다.")
                break
                
            elif choice == '1':
                # 의존성 확인
                missing = check_dependencies()
                if missing:
                    print(f"❌ 필요한 패키지가 설치되지 않았습니다: {', '.join(missing)}")
                    print("먼저 '4. 의존성 설치'를 실행해주세요.")
                    print()
                    continue
                
                run_script('create_excel_with_results.py', 
                          '기본 이미지-결과 매칭 Excel 생성')
                
            elif choice == '2':
                # 의존성 확인
                missing = check_dependencies()
                if missing:
                    print(f"❌ 필요한 패키지가 설치되지 않았습니다: {', '.join(missing)}")
                    print("먼저 '4. 의존성 설치'를 실행해주세요.")
                    print()
                    continue
                
                run_script('create_excel_cell_images.py', 
                          '필터링 최적화 Excel 생성')
                
            elif choice == '3':
                # 의존성 확인
                missing = check_dependencies()
                if missing:
                    print(f"❌ 필요한 패키지가 설치되지 않았습니다: {', '.join(missing)}")
                    print("먼저 '4. 의존성 설치'를 실행해주세요.")
                    print()
                    continue
                
                print("⚠️  주의: 전체 데이터 처리는 시간이 오래 걸릴 수 있습니다.")
                confirm = input("계속하시겠습니까? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    run_script('create_excel_merged.py', 
                              '완전 통합 Excel 생성 (전체 데이터)')
                else:
                    print("작업이 취소되었습니다.")
                
            elif choice == '4':
                install_dependencies()
                
            elif choice == '5':
                setup_venv()
                
            else:
                print("❌ 올바른 번호를 입력해주세요 (0-5)")
            
            print()
            input("계속하려면 Enter 키를 누르세요...")
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")
            print()

if __name__ == "__main__":
    main()