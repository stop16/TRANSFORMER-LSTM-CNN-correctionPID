import numpy as np
from test_transformer_cnn import input_scaler, target_scaler, model  # Scaler와 모델 import

class RealTimePredictor:
    def __init__(self, model, input_scaler, target_scaler, seq_length=5, feature_window=25, threshold=0.3):
        """
        실시간 예측을 하기 위한 초기화:
        - 모델, 스케일러, 시퀀스 길이, 이전 입력값 창 크기(feature_window), 검증 임계값 설정

        +모델과 스케일러 등은 이전에 학습단계에서 설정한 것을 가져와 그대로 사용해야 함

        +시퀀스 길이는 모델을 만들때 정해진 시퀀스 길이를 설정하고 (ex 5) 5개씩 입력값을 받아와 예측을 수행했기 때문에 필요함.
         실시간으로 예측할 때에도 5개씩 받아와서 예측하기 위함.
        
        +이전 입력창과 검증 임계값은 예측한 값을 그대로 사용해도 되는 지 검증하기 위해 필요함.
         이전 입력창 크기를 25개로 설정한 것은 최근 25개의 입력값을 저장하기 위함. 더 변화에 민감하게 만들고 싶으면 이 수를 줄이면 됨. 

        +임계값은 조정 필요
        """
        self.model = model
        self.input_scaler = input_scaler
        self.target_scaler = target_scaler
        self.seq_length = seq_length
        self.recent_inputs = []  # 최근 입력값을 저장할 리스트

        self.feature_window = feature_window  # 평균 비교를 위한 입력값 창 크기
        self.feature_window_inputs = []  # 입력값 평균 비교를 위한 저장소
        self.threshold = threshold  # 입력값 변화 검증을 위한 임계값

    def preprocess_input(self, raw_input):
        """
        입력 데이터를 스케일링 처리:
        - 실시간으로 입력받은 원본 데이터를 모델이 처리할 수 있는 스케일로 변환.
        + -1~ 1 사이로 스케일링.
        """
        scaled_input = self.input_scaler.transform([raw_input])
        return scaled_input.flatten()  # 1D 배열로 반환 (저장 및 처리를 간편하게 하기 위함)

    def update_recent_inputs(self, input_features): 
        """
        최근 입력값 업데이트:
        - 새로운 입력값을 최근 입력 리스트에 추가.
        - 리스트의 크기를 seq_length로 유지하며, 초과된 값은 제거.
        """
        self.recent_inputs.append(input_features)
        if len(self.recent_inputs) > self.seq_length:
            self.recent_inputs.pop(0)  # 가장 오래된 값을 제거 (선입선출)

    def update_feature_window(self, input_features): # 검증하는 데 필요한 최근 feature_widow 만큼의 데이터를 저장 
        """
        이전 입력값 창 업데이트:
        - 평균 비교를 위해 입력값을 별도 리스트에 저장하고, feature_window 크기를 유지.
        """
        self.feature_window_inputs.append(input_features)
        if len(self.feature_window_inputs) > self.feature_window:
            self.feature_window_inputs.pop(0)  # 가장 오래된 값을 제거

    def validate_prediction(self):
        """
        예측 값 검증:
        - 현재 예측에 사용된 입력값(5개)을 제외한 이전 입력값(최근 25개 중 20개)의 평균과 비교.
        - 입력값 변화가 정당한지 확인.
        """
        if len(self.feature_window_inputs) < self.feature_window:
            print("Not enough historical data to validate prediction. Skipping validation.")
            return True  # 초기 상태에서는 검증 없이 진행 (데이터가 충분하지 않음)
    
        # 최근 입력값 (5개)을 제외한 데이터 추출. 
        # 최근 25개 입력값중 현재 target값을 예측하는데 사용한 값들을 빼고 평균을 구하는 과정
        feature_window_array = np.array(self.feature_window_inputs)
        data_for_mean = feature_window_array[:-self.seq_length]  # 최근 5개 제외

        # 평균 계산
        recent_mean = np.mean(data_for_mean, axis=0)

        # 최근 입력값 (5개 전체) 가져오기. 이 값들이 현재 target값을 구하는데 사용된 값들
        recent_inputs_array = np.array(self.recent_inputs)  # (seq_length, features)
    
        # 각 입력값과 평균의 차이 계산
        diff = np.abs(recent_inputs_array - recent_mean)  # 차이 계산

        # 모든 입력값의 차이가 임계값 이내인지 확인. 임계값보다 클 때 target값이 달라지는 것이 맞다고 판단. (입력값들이 차이가 별로 안나는데 target만 바뀌면 이상)
        if np.all(diff < self.threshold):
            print("Prediction validated: Current features align with recent trends.")
            return False
        else:
            print(f"Prediction warning: Current features deviate significantly from recent trends.")
            print(f"Recent Mean (excluding current inputs): {recent_mean}")
            print(f"Recent Inputs: {recent_inputs_array}")
            print(f"Differences: {diff}")
            return True


    def predict_target(self): 
        """
        타겟 값 예측:
        - 최근 입력값이 seq_length에 도달했을 때 모델에 전달하여 타겟 값을 예측합니다.

        import한 예측 모델로 target값을 예측하는 과정
        """
        if len(self.recent_inputs) < self.seq_length:
            print(f"Not enough data to form a sequence. Waiting for {self.seq_length - len(self.recent_inputs)} more inputs.")
            return None

        # 시퀀스 생성 및 모델 입력 준비
        input_sequence = np.array(self.recent_inputs)
        input_sequence = np.expand_dims(input_sequence, axis=0)  # (1, seq_length, features) 형태로 변환. 1은 배치 크기로 실시간 예측시 5개의 입력을 받아 한 번의 예측을 수행하기 때문에 1임.
        scaled_prediction = self.model.predict(input_sequence)
        prediction = self.target_scaler.inverse_transform(scaled_prediction)
        return prediction.flatten()[0]  # 예측값 반환

    def run_real_time_prediction(self):
        """
        실시간으로 입력 데이터를 받아 예측 수행:
        - 사용자로부터 쉼표(,)로 구분된 데이터를 입력받아 처리합니다.
        - 입력값이 충분하지 않을 경우 추가 입력을 요청합니다.
        - 충분한 입력값이 제공되면 타겟 값을 예측하고 검증합니다.
        """
        print("Real-Time Prediction Started. Enter input features (comma-separated).")
        print(f"Input should be in the format: Open, High, Low (e.g., 4300, 4350, 4280)")

        while True:
            try:
                raw_input = input("Enter features (Open, High, Low): ").strip()
                if raw_input.lower() == "exit":
                    print("Exiting prediction system.")
                    break

                # 사용자 입력 처리
                input_features = np.array([float(x) for x in raw_input.split(",")])
                scaled_features = self.preprocess_input(input_features)

                # 최근 입력값 업데이트
                self.update_recent_inputs(scaled_features)
                self.update_feature_window(scaled_features)

                # 타겟 예측
                predicted_target = self.predict_target()
                if predicted_target is not None:
                    print(f"Predicted Target: {predicted_target:.2f}")

                    # 예측 검증
                    is_valid = self.validate_prediction(scaled_features)
                    if not is_valid:
                        print("Warning: Significant deviation detected. Please check input data.")
            except ValueError:
                print("Invalid input. Please enter numeric values separated by commas (e.g., 4300, 4350, 4280).")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    # test_transformer_cnn.py에서 정의된 Scaler와 모델을 가져와 사용
    predictor = RealTimePredictor(model=model, input_scaler=input_scaler, target_scaler=target_scaler)
    predictor.run_real_time_prediction()




# 위는 직접 입력값을 입력해서 예측을 수행하는 코드. 아래는 csv파일로 받아와서 예측하는 코드
'''
def run_real_time_prediction_from_csv(self, csv_file):
    """
    CSV 파일로부터 입력 데이터를 받아 예측 수행:
    - CSV 파일의 각 행을 입력 데이터로 처리.
    """
    print(f"Starting prediction using CSV file: {csv_file}")
    
    try:
        # CSV 파일 로드
        data = pd.read_csv(csv_file)
        features = ['Open', 'High', 'Low']  # 입력 데이터 열 이름. 이건 test에 쓰인 데이터의 열 이름이고 실제로 쓸 땐 우리 데이터에 맞게 수정 필요.
        inputs = data[features].values  # 입력 데이터 추출
        
        for raw_input in inputs:
            scaled_features = self.preprocess_input(raw_input)

            # 최근 입력값 업데이트
            self.update_recent_inputs(scaled_features)
            self.update_feature_window(scaled_features)

            # 타겟 예측
            predicted_target = self.predict_target()
            if predicted_target is not None:
                print(f"Predicted Target: {predicted_target:.2f}")

                # 예측 검증
                is_valid = self.validate_prediction()
                if not is_valid:
                    print("Warning: Significant deviation detected. Please check input data.")
    except Exception as e:
        print(f"Error: {e}")

    if __name__ == "__main__":
        # test_transformer_cnn.py에서 정의된 Scaler와 모델을 가져와 사용
        predictor = RealTimePredictor(model=model, input_scaler=input_scaler, target_scaler=target_scaler)
        predictor.run_real_time_prediction_from_csv("new_data.csv")

'''